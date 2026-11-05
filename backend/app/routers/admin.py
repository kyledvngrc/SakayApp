"""Admin endpoints: manage stops, routes and fare rules.   (IMPERATIVE PARADIGM)

Every write runs in one transaction, then reloads the network so Prolog
immediately reflects the change. All endpoints need an admin token.
"""

from __future__ import annotations

import functools
import json

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Response

from .. import auth, db, geo, services
from ..geo import LatLng
from ..schemas import FareRuleIn, LoginIn, RouteIn, StopIn, StopPatch

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
        except psycopg2.errors.ForeignKeyViolation:
            raise HTTPException(409, "Still in use by a route; remove it from the route first")
        except psycopg2.errors.CheckViolation as e:
            raise HTTPException(422, f"Invalid value: {e.diag.constraint_name}")
    return wrapper


def _route_path(cur, route_id: int) -> tuple[LatLng, ...] | None:
    cur.execute("SELECT path_geojson FROM routes WHERE id = %s", (route_id,))
    row = cur.fetchone()
    return geo.geojson_path(row["path_geojson"]) if row else None


def _recompute_distances(cur, route_id: int) -> None:
    """Refresh distance_from_prev_km for a route from its path and stop positions."""
    cur.execute("""SELECT rs.sequence_no, s.lat, s.lng FROM route_stops rs
                   JOIN stops s ON s.id = rs.stop_id
                   WHERE rs.route_id = %s ORDER BY rs.sequence_no""", (route_id,))
    rows = cur.fetchall()
    distances = geo.stop_distances_km(_route_path(cur, route_id),
                                      [LatLng(r["lat"], r["lng"]) for r in rows])
    for row, km in zip(rows, distances):
        cur.execute("""UPDATE route_stops SET distance_from_prev_km = %s
                       WHERE route_id = %s AND sequence_no = %s""",
                    (km, route_id, row["sequence_no"]))


def _reload() -> dict:
    return services.reload_network()


# --- Overview -----------------------------------------------------------------

@router.get("/data")
def admin_data() -> dict:
    """Everything the admin page needs, including inactive routes."""
    stops = db.fetch_all("""SELECT id, name, landmark, is_landmark, lat, lng, data_source,
                                   collected_on::text AS collected_on
                            FROM stops ORDER BY id""")
    routes = db.fetch_all("""SELECT id, code, name, color, vehicle_type::text AS vehicle_type,
                                    is_bidirectional, is_active, path_geojson, data_source,
                                    collected_on::text AS collected_on
                             FROM routes ORDER BY code""")
    links = db.fetch_all("""SELECT route_id, stop_id, distance_from_prev_km::float AS km
                            FROM route_stops ORDER BY route_id, sequence_no""")
    for r in routes:
        r["stops"] = [{"id": l["stop_id"], "km": l["km"]} for l in links if l["route_id"] == r["id"]]
        r["total_km"] = round(sum(s["km"] for s in r["stops"]), 3)
    fares = db.fetch_all("""SELECT id, vehicle_type::text AS vehicle_type, base_fare::float,
                                   base_km::float, per_km_rate::float, discount_rate::float,
                                   effective_date::text AS effective_date, source, is_placeholder
                            FROM fare_rules ORDER BY vehicle_type, effective_date DESC""")
    return {"stops": stops, "routes": routes, "fare_rules": fares}


@router.post("/reload")
def reload_network() -> dict:
    return _reload()


# --- Stops --------------------------------------------------------------------

@router.post("/stops", status_code=201)
@_db_errors
def create_stop(body: StopIn) -> dict:
    with db.transaction() as cur:
        cur.execute("""INSERT INTO stops (name, landmark, is_landmark, lat, lng, data_source,
                                          collected_on)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (body.name, body.landmark, body.is_landmark, body.lat, body.lng,
                     body.data_source, body.collected_on))
        stop_id = cur.fetchone()["id"]
    _reload()
    return {"id": stop_id}


@router.patch("/stops/{stop_id}")
@_db_errors
def update_stop(stop_id: int, body: StopPatch) -> dict:
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return {"id": stop_id}
    columns = ", ".join(f"{name} = %s" for name in changes)      # names come from the schema
    with db.transaction() as cur:
        cur.execute(f"UPDATE stops SET {columns} WHERE id = %s RETURNING id",
                    (*changes.values(), stop_id))
        if cur.fetchone() is None:
            raise HTTPException(404, "Stop not found")
        if "lat" in changes or "lng" in changes:                  # moved: distances change
            cur.execute("SELECT DISTINCT route_id FROM route_stops WHERE stop_id = %s", (stop_id,))
            for row in cur.fetchall():
                _recompute_distances(cur, row["route_id"])
    _reload()
    return {"id": stop_id}


@router.delete("/stops/{stop_id}", status_code=204)
@_db_errors
def delete_stop(stop_id: int) -> Response:
    with db.transaction() as cur:
        cur.execute("DELETE FROM stops WHERE id = %s RETURNING id", (stop_id,))
        if cur.fetchone() is None:
            raise HTTPException(404, "Stop not found")
    _reload()
    return Response(status_code=204)


# --- Routes -------------------------------------------------------------------

def _save_route(cur, route_id: int | None, body: RouteIn) -> int:
    path = ({"type": "LineString", "coordinates": [[p.lng, p.lat] for p in body.path]}
            if len(body.path) >= 2 else None)
    values = (body.code, body.name, body.color, body.vehicle_type, body.is_bidirectional,
              body.is_active, json.dumps(path) if path else None, body.data_source,
              body.collected_on)
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
    route_id = row["id"]

    # Resolve each stop: reuse an existing id or create the new stop.
    stop_ids: list[int] = []
    for ref in body.stops:
        if ref.id is not None:
            cur.execute("SELECT id FROM stops WHERE id = %s", (ref.id,))
            if cur.fetchone() is None:
                raise HTTPException(422, f"Stop {ref.id} does not exist")
            stop_ids.append(ref.id)
        else:
            cur.execute("""INSERT INTO stops (name, is_landmark, lat, lng, data_source, collected_on)
                           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                        (ref.name, ref.is_landmark, ref.lat, ref.lng, body.data_source,
                         body.collected_on))
            stop_ids.append(cur.fetchone()["id"])
    if len(stop_ids) != len(set(stop_ids)):
        raise HTTPException(422, "A stop can appear only once on a route")

    cur.execute("DELETE FROM route_stops WHERE route_id = %s", (route_id,))
    for seq, stop_id in enumerate(stop_ids, start=1):
        cur.execute("""INSERT INTO route_stops (route_id, stop_id, sequence_no)
                       VALUES (%s, %s, %s)""", (route_id, stop_id, seq))
    _recompute_distances(cur, route_id)
    return route_id


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
                                               discount_rate, effective_date, source, is_placeholder)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (body.vehicle_type, body.base_fare, body.base_km, body.per_km_rate,
                     body.discount_rate, body.effective_date, body.source, body.is_placeholder))
        rule_id = cur.fetchone()["id"]
    _reload()
    return {"id": rule_id}


@router.put("/fare-rules/{rule_id}")
@_db_errors
def update_fare_rule(rule_id: int, body: FareRuleIn) -> dict:
    with db.transaction() as cur:
        cur.execute("""UPDATE fare_rules SET vehicle_type = %s, base_fare = %s, base_km = %s,
                              per_km_rate = %s, discount_rate = %s, effective_date = %s,
                              source = %s, is_placeholder = %s
                       WHERE id = %s RETURNING id""",
                    (body.vehicle_type, body.base_fare, body.base_km, body.per_km_rate,
                     body.discount_rate, body.effective_date, body.source, body.is_placeholder,
                     rule_id))
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
