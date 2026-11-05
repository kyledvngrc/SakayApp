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

# Sample network from conftest.py (test database only): R01 runs north to a
# corner, R02 runs east from it; the fare rule is a placeholder.
A = {"lat": 7.0700, "lng": 125.6102}            # ~22 m east of where R01 starts
E = {"lat": 7.0801, "lng": 125.6200}            # ~11 m north of where R02 ends


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["routes"] == 2 and body["landmarks"] == 2
    assert body["transfer_points"] >= 2                         # R01 <-> R02 at the corner


def test_routes_and_landmarks(client):
    routes = {r["code"]: r for r in client.get("/routes").json()}
    assert set(routes) == {"R01", "R02"}
    assert routes["R01"]["kind"] == "both" and routes["R01"]["length_km"] == pytest.approx(1.11, abs=0.01)
    assert client.get("/routes/R01").json()["path_geojson"]["type"] == "LineString"
    assert client.get("/routes/NOPE").status_code == 404
    assert {lm["name"] for lm in client.get("/landmarks").json()} == {"Sample Corner", "Sample Plaza"}


def test_nearby_routes(client):
    found = client.get("/routes/nearby", params=A).json()
    assert [r["code"] for r in found] == ["R01"] and found[0]["walk_m"] == 22


def test_plan_with_transfer(client):
    body = client.post("/trips/plan", json={"origin": A, "destination": E}).json()
    best = body["trips"][0]
    assert best["route_codes"] == ["R01", "R02"] and best["transfers"] == 1
    assert best["fare_available"] is False and best["total_fare"] is None   # placeholder fare
    assert body["notice"] is None and "minutes" not in best
    texts = [seg["instruction"] for seg in best["segments"]]
    assert texts == ["Walk 20 m to the Plaza - Corner route at Sample Plaza",
                     "Ride Plaza - Corner toward Corner and get off at Sample Corner, about 1.1 km",
                     "Transfer to Corner - East End toward East End and get off after about 1.1 km",
                     "Walk 10 m to your destination"]


def test_plan_far_away(client):
    body = client.post("/trips/plan", json={"origin": {"lat": 7.2, "lng": 125.6},
                                            "destination": E}).json()
    assert body["trips"] == [] and "starting point" in body["notice"]


def test_plan_within_walking_distance(client):
    body = client.post("/trips/plan", json={"origin": A,
                                            "destination": {"lat": 7.0720, "lng": 125.6100}}).json()
    assert body["notice"] == "Your destination is within walking distance."


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
