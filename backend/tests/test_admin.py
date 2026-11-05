"""Admin API tests against the live database. Creates and removes its own data."""
import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.config import settings

try:
    psycopg2.connect(settings.database_url).close()
except psycopg2.OperationalError:
    pytest.skip("database not running", allow_module_level=True)

from app import auth, db  # noqa: E402
from app.main import app  # noqa: E402

EMAIL, PASSWORD = "pytest-admin@example.test", "pytest-password-123"
D = 0.0018                     # ~200 m of latitude


@pytest.fixture(scope="module")
def client():
    with db.transaction() as cur:
        cur.execute("""INSERT INTO users (email, password_hash, role) VALUES (%s, %s, 'admin')
                       ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash""",
                    (EMAIL, auth.hash_password(PASSWORD)))
        cur.execute("""INSERT INTO users (email, password_hash, role) VALUES (%s, %s, 'commuter')
                       ON CONFLICT (email) DO NOTHING""",
                    ("pytest-commuter@example.test", auth.hash_password(PASSWORD)))
    with TestClient(app) as c:
        yield c
    with db.transaction() as cur:
        cur.execute("DELETE FROM routes WHERE code LIKE 'PYT%'")
        cur.execute("DELETE FROM stops WHERE name LIKE 'pytest %'")
        cur.execute("DELETE FROM fare_rules WHERE source LIKE 'pytest%'")
        cur.execute("DELETE FROM users WHERE email LIKE 'pytest-%'")
    from app import services
    services.reload_network()


@pytest.fixture(scope="module")
def headers(client):
    token = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def route_body(code="PYT1", **over):
    lat0, lng = 7.0950, 125.6300                     # away from the seed stops
    body = {
        "code": code, "name": "pytest route", "color": "#123456",
        "path": [{"lat": lat0, "lng": lng}, {"lat": lat0 + 3 * D, "lng": lng}],
        "stops": [{"name": f"pytest {code} s{i}", "lat": lat0 + i * D, "lng": lng} for i in range(4)],
        "data_source": "pytest", "collected_on": "2026-11-05",
    }
    return {**body, **over}


def test_login_rules(client):
    assert client.post("/auth/login", json={"email": EMAIL, "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", json={"email": "pytest-commuter@example.test",
                                            "password": PASSWORD}).status_code == 403
    assert client.post("/auth/login", json={"email": EMAIL.upper(), "password": PASSWORD}).status_code == 200


def test_admin_requires_token(client):
    assert client.get("/admin/data").status_code == 401
    assert client.get("/admin/data", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_admin_page_served(client):
    res = client.get("/admin")
    assert res.status_code == 200 and "SakayApp Admin" in res.text
    assert client.get("/admin-static/admin.js").status_code == 200


def test_create_route_then_plan_trip(client, headers):
    res = client.post("/admin/routes", json=route_body(), headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["network"]["routes"] == 3

    data = client.get("/admin/data", headers=headers).json()
    route = next(r for r in data["routes"] if r["code"] == "PYT1")
    assert len(route["stops"]) == 4 and route["stops"][0]["km"] == 0
    assert route["total_km"] == pytest.approx(0.6, abs=0.01)       # 3 hops x ~200 m along the line

    plan = client.post("/trips/plan?log_search=false", json={
        "origin": {"lat": 7.0950, "lng": 125.6300},
        "destination": {"lat": 7.0950 + 3 * D, "lng": 125.6300}}).json()
    assert plan["trips"][0]["route_codes"] == ["PYT1"]


def test_second_route_reuses_stop_for_transfer(client, headers):
    data = client.get("/admin/data", headers=headers).json()
    route1 = next(r for r in data["routes"] if r["code"] == "PYT1")
    shared_id = route1["stops"][-1]["id"]
    shared = next(s for s in data["stops"] if s["id"] == shared_id)
    body = route_body("PYT2", path=[], stops=[
        {"id": shared_id},
        {"name": "pytest PYT2 east", "lat": shared["lat"], "lng": shared["lng"] + 4 * D}])   # ~800 m: too far to walk
    assert client.post("/admin/routes", json=body, headers=headers).status_code == 201

    plan = client.post("/trips/plan?log_search=false", json={
        "origin": {"lat": 7.0950, "lng": 125.6300},
        "destination": {"lat": shared["lat"], "lng": shared["lng"] + 4 * D}}).json()
    assert plan["trips"][0]["route_codes"] == ["PYT1", "PYT2"]


def test_update_route_and_deactivate(client, headers):
    data = client.get("/admin/data", headers=headers).json()
    route = next(r for r in data["routes"] if r["code"] == "PYT2")
    body = route_body("PYT2", path=[], is_active=False,
                      stops=[{"id": s["id"]} for s in route["stops"]])
    res = client.put(f"/admin/routes/{route['id']}", json=body, headers=headers)
    assert res.status_code == 200 and res.json()["network"]["routes"] == 3     # 2 seed + PYT1
    assert "PYT2" not in {r["code"] for r in client.get("/routes").json()}


def test_route_validation(client, headers):
    assert client.post("/admin/routes", json=route_body("bad code"), headers=headers).status_code == 422
    one_stop = route_body("PYT3", stops=[{"name": "pytest x", "lat": 7.1, "lng": 125.6}])
    assert client.post("/admin/routes", json=one_stop, headers=headers).status_code == 422
    dup = route_body("PYT3", stops=[{"id": 1}, {"id": 1}])
    assert client.post("/admin/routes", json=dup, headers=headers).status_code == 422
    missing = route_body("PYT3", stops=[{"id": 1}, {"id": 999999}])
    assert client.post("/admin/routes", json=missing, headers=headers).status_code == 422
    assert client.post("/admin/routes", json=route_body("PYT1"), headers=headers).status_code == 409


def test_moving_a_stop_updates_distances(client, headers):
    data = client.get("/admin/data", headers=headers).json()
    route = next(r for r in data["routes"] if r["code"] == "PYT2")     # no path: straight lines
    moved = route["stops"][1]["id"]
    stop = next(s for s in data["stops"] if s["id"] == moved)
    assert client.patch(f"/admin/stops/{moved}", json={"lng": stop["lng"] + D},
                        headers=headers).status_code == 200
    data = client.get("/admin/data", headers=headers).json()
    after = next(r for r in data["routes"] if r["code"] == "PYT2")
    assert after["total_km"] == pytest.approx(5 / 4 * route["total_km"], rel=0.02)   # 4D east -> 5D east


def test_stop_in_use_cannot_be_deleted(client, headers):
    data = client.get("/admin/data", headers=headers).json()
    used = next(r for r in data["routes"] if r["code"] == "PYT1")["stops"][0]["id"]
    assert client.delete(f"/admin/stops/{used}", headers=headers).status_code == 409
    new = client.post("/admin/stops", json={"name": "pytest lonely", "lat": 7.11, "lng": 125.64},
                      headers=headers).json()["id"]
    assert client.delete(f"/admin/stops/{new}", headers=headers).status_code == 204
    assert client.delete(f"/admin/stops/{new}", headers=headers).status_code == 404


def test_fare_rule_lifecycle(client, headers):
    """Values are test fixtures, not real fares."""
    body = {"vehicle_type": "jeepney", "base_fare": "10.00", "base_km": "4", "per_km_rate": "1.50",
            "discount_rate": "0.2", "effective_date": "2001-01-01", "source": "pytest fixture"}
    rule_id = client.post("/admin/fare-rules", json=body, headers=headers).json()["id"]
    plan = client.post("/trips/plan?log_search=false", json={
        "origin": {"lat": 7.0950, "lng": 125.6300},
        "destination": {"lat": 7.0950 + 3 * D, "lng": 125.6300}, "rider_type": "student"}).json()
    assert plan["trips"][0]["total_fare"] == 8.0 and plan["fare_source"] == "pytest fixture"
    assert client.post("/admin/fare-rules", json=body, headers=headers).status_code == 409
    assert client.delete(f"/admin/fare-rules/{rule_id}", headers=headers).status_code == 204


def test_delete_route(client, headers):
    data = client.get("/admin/data", headers=headers).json()
    route = next(r for r in data["routes"] if r["code"] == "PYT1")
    assert client.delete(f"/admin/routes/{route['id']}", headers=headers).status_code == 204
    assert client.delete(f"/admin/routes/{route['id']}", headers=headers).status_code == 404
