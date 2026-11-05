"""Place search: pure formatting, and the endpoint with the geocoder stubbed out."""
import pytest

from app import places
from app.models import Landmark

MALL = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [125.6307, 7.0989]},
        "properties": {"name": "SM Lanang Premier", "street": "J. P. Laurel Avenue",
                       "district": "Lanang", "city": "Davao City"}}
CINEMA_SAME_NAME = {**MALL, "geometry": {"type": "Point", "coordinates": [125.6309, 7.0990]}}
STREET_ONLY = {"geometry": {"coordinates": [125.6, 7.07]}, "properties": {"street": "Quimpo Blvd", "city": "Davao City"}}
NO_POINT = {"geometry": {}, "properties": {"name": "Nowhere"}}


def test_place_detail_skips_empty_and_repeats():
    assert places.place_detail(MALL["properties"]) == "J. P. Laurel Avenue, Lanang, Davao City"
    assert places.place_detail({"name": "Bankerohan", "district": "Bankerohan", "city": "Davao City"}) == "Davao City"


def test_places_from_features_dedupes_and_skips_bad():
    found = places.places_from_features([MALL, CINEMA_SAME_NAME, STREET_ONLY, NO_POINT], limit=8)
    assert [p["name"] for p in found] == ["SM Lanang Premier", "Quimpo Blvd"]
    assert found[0]["lat"] == 7.0989 and found[0]["source"] == "osm"


def test_landmark_matches_case_insensitive():
    lms = [Landmark(1, "Bankerohan Market", 7.07, 125.6, "public market"), Landmark(2, "Ateneo", 7.07, 125.6)]
    assert [m["name"] for m in places.landmark_matches(lms, "MARKET", 5)] == ["Bankerohan Market"]


@pytest.fixture
def client(monkeypatch):
    import psycopg2
    from app.config import settings
    try:
        psycopg2.connect(settings.database_url).close()
    except psycopg2.OperationalError:
        pytest.skip("database not running")
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import places as router
    calls = []

    def fake_photon(path, params):
        calls.append((path, params))
        if params.get("q") == "boom":
            raise TimeoutError
        return [MALL]

    monkeypatch.setattr(router, "_photon", fake_photon)
    router._search_osm.cache_clear()
    router._reverse_osm.cache_clear()
    with TestClient(app) as c:
        c.calls = calls
        yield c


def test_search_landmarks_first_then_osm(client):
    body = client.get("/places/search", params={"q": "sample"}).json()
    assert [r["source"] for r in body["results"]][:2] == ["landmark", "landmark"]
    assert body["results"][-1]["name"] == "SM Lanang Premier" and body["search_available"]
    assert "lat" not in client.calls[0][1] or client.calls[0][1]["lat"] == 7.0731   # city centre, not the user


def test_search_is_cached(client):
    client.get("/places/search", params={"q": "SM Lanang"})
    client.get("/places/search", params={"q": "sm  lanang"})
    assert len(client.calls) == 1


def test_search_survives_geocoder_failure(client):
    body = client.get("/places/search", params={"q": "boom"}).json()
    assert body["results"] == [] and body["search_available"] is False


def test_reverse_prefers_landmark(client):
    assert client.get("/places/reverse", params={"lat": 7.0800, "lng": 125.6101}).json() == {"label": "Near Sample Corner"}
    label = client.get("/places/reverse", params={"lat": 7.2, "lng": 125.6}).json()["label"]
    assert label == "Near SM Lanang Premier, J. P. Laurel Avenue"
