"""Loading the network into the planner.                   (IMPERATIVE PARADIGM)

Reads the database, asserts every leg into Prolog, and swaps in a fresh
TripPlanner. Called at startup and after admins change route data.
"""

from __future__ import annotations

import logging
import threading

from . import db, prolog_bridge
from .config import settings
from .models import TripPlanner

log = logging.getLogger("sakay")
_lock = threading.Lock()
_planner: TripPlanner | None = None


def reload_network() -> dict:
    global _planner
    with _lock:
        network = db.load_network()
        prolog_bridge.start(settings.prolog_rules_path)
        leg_count = prolog_bridge.load_legs(network.legs)
        _planner = TripPlanner(network, prolog_bridge.find_trips, settings)
    summary = {"stops": len(network.stops), "routes": len(network.routes), "legs": leg_count}
    log.info("network loaded: %s", summary)
    return summary


def planner() -> TripPlanner:
    if _planner is None:
        raise RuntimeError("network not loaded yet")
    return _planner
