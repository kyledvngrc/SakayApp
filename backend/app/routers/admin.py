"""Admin endpoints: manage routes, landmarks and fare rules. (IMPERATIVE PARADIGM)

Every write runs in one transaction, then reloads the network so Prolog
immediately reflects the change. All endpoints need an admin token.
"""

from __future__ import annotations

import functools
import json

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Response

from .. import auth, db, geo, services
from ..schemas import FareRuleIn, LandmarkIn, LandmarkPatch, LoginIn, RouteIn

public = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)])


# --- Auth ---------------------------------------------------------------------

@public.post("/login")
def login(body: LoginIn) -> dict:
    user = auth.authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(401, "Wrong email or password")
    if user["role"] != "admin":
        raise HTTPException(403, "This account is not an admin")
    return {"token": auth.create_token(user["id"], user["role"]), "email": user["email"]}


# --- Helpers ------------------------------------------------------------------

def _db_errors(fn):
    """Turn constraint violations into readable HTTP errors."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except psycopg2.errors.UniqueViolation as e:
            raise HTTPException(409, f"Already exists: {e.diag.message_detail or e.diag.message_primary}")
        except psycopg2.errors.CheckViolation as e:
            raise HTTPException(422, f"Invalid value: {e.diag.constraint_name}")
    return wrapper


def _reload() -> dict:
    return services.reload_network()


# --- Overview -----------------------------------------------------------------

@router.get("/data")
def admin_data() -> dict:
    """Everything the admin page needs, including inactive routes."""
    landmarks = db.fetch_all("""SELECT id, name, description, lat, lng, data_source,
                                       collected_on::text AS collected_on
                                FROM landmarks ORDER BY name""")
    routes = db.fetch_all("""SELECT id, code, name, color, vehicle_type::text AS vehicle_type,
                                    is_bidirectional, is_active, path_geojson, data_source,
                                    collected_on::text AS collected_on
                             FROM routes ORDER BY code""")
    network = services.planner().network
    for r in routes:
        live = network.routes.get(r["code"])
        path = geo.geojson_path(r["path_geojson"]) or ()
        r["length_km"] = round(geo.cumulative_m(path)[-1] / 1000, 2) if path else 0
        r["kind"] = live.kind if live else None
    fares = db.fetch_all("""SELECT id, vehicle_type::text AS vehicle_type, base_fare::float,
                                   base_km::float, per_km_rate::float, discounted_base_fare::float,
                                   discounted_per_km_rate::float,
                                   effective_date::text AS effective_date, source, is_placeholder
                            FROM fare_rules ORDER BY vehicle_type, effective_date DESC""")
    transfers = [{"from": l.from_route, "to": l.to_route, "walk_m": round(l.walk_m),
                  "lat": l.from_point.lat, "lng": l.from_point.lng}
                 for l in network.links]
    return {"landmarks": landmarks, "routes": routes, "fare_rules": fares,
            "transfer_points": transfers}


@router.post("/reload")
def reload_network() -> dict:
    return _reload()


# --- Landmarks ----------------------------------------------------------------

@router.post("/landmarks", status_code=201)
@_db_errors
def create_landmark(body: LandmarkIn) -> dict:
    with db.transaction() as cur:
        cur.execute("""INSERT INTO landmarks (name, description, lat, lng, data_source, collected_on)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                    (body.name, body.description, body.lat, body.lng, body.data_source,
                     body.collected_on))
        landmark_id = cur.fetchone()["id"]
    _reload()
    return {"id": landmark_id}


@router.patch("/landmarks/{landmark_id}")
@_db_errors
def update_landmark(landmark_id: int, body: LandmarkPatch) -> dict:
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return {"id": landmark_id}
    columns = ", ".join(f"{name} = %s" for name in changes)      # names come from the schema
    with db.transaction() as cur:
        cur.execute(f"UPDATE landmarks SET {columns} WHERE id = %s RETURNING id",
                    (*changes.values(), landmark_id))
        if cur.fetchone() is None:
            raise HTTPException(404, "Landmark not found")
    _reload()
    return {"id": landmark_id}


@router.delete("/landmarks/{landmark_id}", status_code=204)
@_db_errors
def delete_landmark(landmark_id: int) -> Response:
    with db.transaction() as cur:
        cur.execute("DELETE FROM landmarks WHERE id = %s RETURNING id", (landmark_id,))
        if cur.fetchone() is None:
            raise HTTPException(404, "Landmark not found")
    _reload()
    return Response(status_code=204)


# --- Routes -------------------------------------------------------------------

def _save_route(cur, route_id: int | None, body: RouteIn) -> int:
    path = {"type": "LineString", "coordinates": [[p.lng, p.lat] for p in body.path]}
    values = (body.code, body.name, body.color, body.vehicle_type, body.is_bidirectional,
              body.is_active, json.dumps(path), body.data_source, body.collected_on)
    if route_id is None:
        cur.execute("""INSERT INTO routes (code, name, color, vehicle_type, is_bidirectional,
                                           is_active, path_geojson, data_source, collected_on)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""", values)
    else:
        cur.execute("""UPDATE routes SET code = %s, name = %s, color = %s, vehicle_type = %s,
                              is_bidirectional = %s, is_active = %s, path_geojson = %s,
                              data_source = %s, collected_on = %s
                       WHERE id = %s RETURNING id""", (*values, route_id))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(404, "Route not found")
    return row["id"]


@router.post("/routes", status_code=201)
@_db_errors
def create_route(body: RouteIn) -> dict:
    with db.transaction() as cur:
        route_id = _save_route(cur, None, body)
    return {"id": route_id, "network": _reload()}


@router.put("/routes/{route_id}")
@_db_errors
def update_route(route_id: int, body: RouteIn) -> dict:
    with db.transaction() as cur:
        _save_route(cur, route_id, body)
    return {"id": route_id, "network": _reload()}


@router.delete("/routes/{route_id}", status_code=204)
@_db_errors
def delete_route(route_id: int) -> Response:
    with db.transaction() as cur:
        cur.execute("DELETE FROM routes WHERE id = %s RETURNING id", (route_id,))
        if cur.fetchone() is None:
            raise HTTPException(404, "Route not found")
    _reload()
    return Response(status_code=204)


# --- Fare rules ---------------------------------------------------------------

@router.post("/fare-rules", status_code=201)
@_db_errors
def create_fare_rule(body: FareRuleIn) -> dict:
    with db.transaction() as cur:
        cur.execute("""INSERT INTO fare_rules (vehicle_type, base_fare, base_km, per_km_rate,
                                               discounted_base_fare, discounted_per_km_rate,
                                               effective_date, source, is_placeholder)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (body.vehicle_type, body.base_fare, body.base_km, body.per_km_rate,
                     body.discounted_base_fare, body.discounted_per_km_rate,
                     body.effective_date, body.source, body.is_placeholder))
        rule_id = cur.fetchone()["id"]
    _reload()
    return {"id": rule_id}


@router.put("/fare-rules/{rule_id}")
@_db_errors
def update_fare_rule(rule_id: int, body: FareRuleIn) -> dict:
    with db.transaction() as cur:
        cur.execute("""UPDATE fare_rules SET vehicle_type = %s, base_fare = %s, base_km = %s,
                              per_km_rate = %s, discounted_base_fare = %s,
                              discounted_per_km_rate = %s, effective_date = %s,
                              source = %s, is_placeholder = %s
                       WHERE id = %s RETURNING id""",
                    (body.vehicle_type, body.base_fare, body.base_km, body.per_km_rate,
                     body.discounted_base_fare, body.discounted_per_km_rate,
                     body.effective_date, body.source, body.is_placeholder, rule_id))
        if cur.fetchone() is None:
            raise HTTPException(404, "Fare rule not found")
    _reload()
    return {"id": rule_id}


@router.delete("/fare-rules/{rule_id}", status_code=204)
@_db_errors
def delete_fare_rule(rule_id: int) -> Response:
    with db.transaction() as cur:
        cur.execute("DELETE FROM fare_rules WHERE id = %s RETURNING id", (rule_id,))
        if cur.fetchone() is None:
            raise HTTPException(404, "Fare rule not found")
    _reload()
    return Response(status_code=204)
