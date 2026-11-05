"""API tests against the live database (docker compose up -d) with seed.sql data."""
import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.config import settings

try:
    psycopg2.connect(settings.database_url).close()
except psycopg2.OperationalError:
    pytest.skip("database not running", allow_module_level=True)

from app.main import app  # noqa: E402

# Seed: R01 A(1)-B(2)-C(3), R02 C(3)-D(4)-E(5); fare rule is a placeholder.
A = {"lat": 7.0700, "lng": 125.6100}
E = {"lat": 7.0820, "lng": 125.6110}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["stops"] == 5 and body["routes"] == 2


def test_routes_and_stops(client):
    routes = {r["code"]: r for r in client.get("/routes").json()}
    assert set(routes) == {"R01", "R02"}
    assert len(routes["R01"]["stop_ids"]) == 3
    detail = client.get("/routes/R01").json()
    assert [s["name"] for s in detail["stops"]] == ["Sample Stop A", "Sample Stop B", "Sample Stop C"]
    assert client.get("/routes/NOPE").status_code == 404


def test_nearby(client):
    found = client.get("/stops/nearby", params=A).json()
    assert found[0]["name"] == "Sample Stop A" and found[0]["distance_m"] == 0


def test_plan_with_transfer(client):
    body = client.post("/trips/plan", json={"origin": A, "destination": E}).json()
    best = body["trips"][0]
    assert best["route_codes"] == ["R01", "R02"] and best["transfers"] == 1
    assert best["fare_available"] is False and best["total_fare"] is None   # placeholder fare
    assert body["notice"] is None
    texts = [seg["instruction"] for seg in best["segments"]]
    assert texts == ["Walk 10 m to Sample Stop A",
                     "Ride R01 (Sample Route 1 (A - C)) and get off at Sample Stop C, about 860 m",
                     "Transfer to R02 (Sample Route 2 (C - E)) and get off at Sample Stop E, about 800 m",
                     "Walk 10 m to your destination"]


def test_plan_far_away(client):
    body = client.post("/trips/plan", json={"origin": {"lat": 7.2, "lng": 125.6},
                                            "destination": E}).json()
    assert body["trips"] == [] and "starting point" in body["notice"]


@pytest.mark.parametrize("payload", [
    {"origin": A, "destination": A},
    {"origin": A, "destination": E, "rider_type": "vip"},
    {"origin": {"lat": 99, "lng": 0}, "destination": E},
])
def test_plan_validation(client, payload):
    assert client.post("/trips/plan", json=payload).status_code == 422


def test_search_is_logged(client):
    from app import db
    before = db.fetch_all("SELECT count(*) AS n FROM search_log")[0]["n"]
    client.post("/trips/plan", json={"origin": A, "destination": E})
    assert db.fetch_all("SELECT count(*) AS n FROM search_log")[0]["n"] == before + 1
