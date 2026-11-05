"""Loading the network into the planner.                   (IMPERATIVE PARADIGM)

Reads the database, works out where routes connect, asserts the routes and
links into Prolog, and swaps in a fresh TripPlanner. Called at startup and
after admins change route data.
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
        network = db.load_network(settings)
        prolog_bridge.start(settings.prolog_rules_path)
        prolog_bridge.load_network(network.routes.values(), network.links)
        _planner = TripPlanner(network, prolog_bridge.best_trips, settings)
    summary = {"routes": len(network.routes), "landmarks": len(network.landmarks),
               "transfer_points": len(network.links)}
    log.info("network loaded: %s", summary)
    return summary


def planner() -> TripPlanner:
    if _planner is None:
        raise RuntimeError("network not loaded yet")
    return _planner
