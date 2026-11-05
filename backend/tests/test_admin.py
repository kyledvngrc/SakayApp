"""Admin API tests against the test database. Creates and removes its own data."""
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
D = 0.0018                     # ~200 m
LAT0, LNG0 = 7.0950, 125.6300  # away from the sample routes


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
        cur.execute("DELETE FROM landmarks WHERE name LIKE 'pytest %'")
        cur.execute("DELETE FROM fare_rules WHERE source LIKE 'pytest%'")
        cur.execute("DELETE FROM users WHERE email LIKE 'pytest-%'")
    from app import services
    services.reload_network()


@pytest.fixture(scope="module")
def headers(client):
    token = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def pt(north=0.0, east=0.0):
    return {"lat": LAT0 + north * D, "lng": LNG0 + east * D}


def route_body(code="PYT1", **over):
    body = {"code": code, "name": "pytest - route", "color": "#123456",
            "path": [pt(0), pt(3)],                                    # ~600 m north
            "data_source": "pytest", "collected_on": "2026-11-05"}
    return {**body, **over}


def plan(client, origin, destination, **extra):
    return client.post("/trips/plan?log_search=false",
                       json={"origin": origin, "destination": destination, **extra}).json()


def admin_route(client, headers, code):
    return next(r for r in client.get("/admin/data", headers=headers).json()["routes"]
                if r["code"] == code)


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
    route = admin_route(client, headers, "PYT1")
    assert route["length_km"] == pytest.approx(0.6, abs=0.01) and route["kind"] == "both"
    assert plan(client, pt(0.2), pt(2.8))["trips"][0]["route_codes"] == ["PYT1"]


def test_crossing_route_gives_transfer(client, headers):
    body = route_body("PYT2", path=[pt(2.9, -3), pt(2.9, 3)], is_bidirectional=False)   # east, crosses PYT1
    assert client.post("/admin/routes", json=body, headers=headers).status_code == 201
    assert admin_route(client, headers, "PYT2")["kind"] == "oneway"
    data = client.get("/admin/data", headers=headers).json()
    assert any(t["from"] == "PYT1" and t["to"] == "PYT2" and t["walk_m"] < 20
               for t in data["transfer_points"])
    trip = plan(client, pt(0), pt(2.9, 2.8))["trips"][0]
    assert trip["route_codes"] == ["PYT1", "PYT2"]
    assert plan(client, pt(2.9, 2.8), pt(2.9, -2.8))["trips"] == []        # PYT2 runs east only


def test_update_route_and_deactivate(client, headers):
    route = admin_route(client, headers, "PYT2")
    body = route_body("PYT2", path=[pt(2.9, -3), pt(2.9, 3)], is_active=False)
    res = client.put(f"/admin/routes/{route['id']}", json=body, headers=headers)
    assert res.status_code == 200 and res.json()["network"]["routes"] == 3     # 2 sample + PYT1
    assert "PYT2" not in {r["code"] for r in client.get("/routes").json()}
    assert admin_route(client, headers, "PYT2")["kind"] is None                # not planned


def test_route_validation(client, headers):
    assert client.post("/admin/routes", json=route_body("bad code"), headers=headers).status_code == 422
    assert client.post("/admin/routes", json=route_body("PYT3", path=[pt(0)]), headers=headers).status_code == 422
    assert client.post("/admin/routes", json=route_body("PYT1"), headers=headers).status_code == 409
    assert client.put("/admin/routes/999999", json=route_body("PYT9"), headers=headers).status_code == 404


def test_landmark_lifecycle_and_directions(client, headers):
    res = client.post("/admin/landmarks", json={"name": "pytest Gate", **pt(3)}, headers=headers)
    assert res.status_code == 201
    landmark_id = res.json()["id"]
    texts = [s["instruction"] for s in plan(client, pt(0.2), pt(2.9))["trips"][0]["segments"]]
    assert "get off at pytest Gate" in texts[1]
    assert client.patch(f"/admin/landmarks/{landmark_id}", json={"name": "pytest Main Gate"},
                        headers=headers).status_code == 200
    texts = [s["instruction"] for s in plan(client, pt(0.2), pt(2.9))["trips"][0]["segments"]]
    assert "get off at pytest Main Gate" in texts[1]
    assert client.delete(f"/admin/landmarks/{landmark_id}", headers=headers).status_code == 204
    assert client.delete(f"/admin/landmarks/{landmark_id}", headers=headers).status_code == 404


def test_fare_rule_lifecycle(client, headers):
    """Values are test fixtures, not real fares."""
    body = {"vehicle_type": "jeepney", "base_fare": "10.00", "base_km": "4", "per_km_rate": "1.50",
            "discounted_base_fare": "8.00", "discounted_per_km_rate": "1.20",
            "effective_date": "2001-01-01", "source": "pytest fixture"}
    rule_id = client.post("/admin/fare-rules", json=body, headers=headers).json()["id"]
    result = plan(client, pt(0.2), pt(2.8), rider_type="student")
    assert result["trips"][0]["total_fare"] == 8.0 and result["fare_source"] == "pytest fixture"
    assert client.post("/admin/fare-rules", json=body, headers=headers).status_code == 409
    too_high = {**body, "effective_date": "2002-01-01", "discounted_base_fare": "10.50"}
    assert client.post("/admin/fare-rules", json=too_high, headers=headers).status_code == 422
    assert client.delete(f"/admin/fare-rules/{rule_id}", headers=headers).status_code == 204


def test_delete_route(client, headers):
    route = admin_route(client, headers, "PYT1")
    assert client.delete(f"/admin/routes/{route['id']}", headers=headers).status_code == 204
    assert client.delete(f"/admin/routes/{route['id']}", headers=headers).status_code == 404
