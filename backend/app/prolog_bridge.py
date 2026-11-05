"""Python <-> SWI-Prolog bridge.                           (IMPERATIVE PARADIGM)

pyswip is not safe to call from several threads at once, so every Prolog call
runs on one dedicated worker thread. Callers block until their call finishes.

Path finding itself stays in prolog/routes.pl; this module only loads facts
(route/3, link/5) and runs queries.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable, Sequence

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prolog")
_prolog: Any = None
_SAFE_CODE = re.compile(r"^[A-Za-z0-9_-]+$")
_KINDS = {"both", "oneway", "loop"}


def _run(fn, *args):
    return _executor.submit(fn, *args).result()


def quote_atom(text: str) -> str:
    """Prolog atom literal for a route code (also rejected if it has odd characters)."""
    if not _SAFE_CODE.match(text):
        raise ValueError(f"route code {text!r} may only contain letters, digits, _ and -")
    return f"'{text}'"


def _start(rules_path: Path) -> None:
    global _prolog
    if _prolog is not None:
        return
    from pyswip import Prolog          # imported here so it initialises on the worker thread
    _prolog = Prolog()
    _prolog.consult(str(rules_path))


def start(rules_path: Path) -> None:
    """Start SWI-Prolog and load the routing rules (safe to call more than once)."""
    _run(_start, rules_path)


def _load_network(routes: list[tuple[str, str, int]],
                  links: list[tuple[str, int, str, int, int]]) -> None:
    list(_prolog.query("routes:clear_network"))
    for code, kind, length in routes:
        _prolog.assertz(f"routes:route({quote_atom(code)}, {kind}, {int(length)})")
    for r1, p1, r2, p2, walk in links:
        _prolog.assertz(f"routes:link({quote_atom(r1)}, {int(p1)}, {quote_atom(r2)}, "
                        f"{int(p2)}, {int(walk)})")


def load_network(routes: Iterable, links: Iterable) -> None:
    """Replace all route/3 and link/5 facts with the given routes and links."""
    route_facts = [(r.code, r.kind, round(r.length_m)) for r in routes]
    if any(kind not in _KINDS for _, kind, _ in route_facts):
        raise ValueError("unknown route kind")
    link_facts = [(l.from_route, round(l.from_m), l.to_route, round(l.to_m), round(l.walk_m))
                  for l in links]
    _run(_load_network, route_facts, link_facts)


def _candidates(functor: str, items: Sequence[tuple[str, int, int]]) -> str:
    return "[" + ",".join(f"{functor}({quote_atom(code)}, {int(pos)}, {int(walk)})"
                          for code, pos, walk in items) + "]"


def _best(starts, goals, max_transfers: int) -> list[list[tuple]]:
    goal = (f"routes:best_trip_rows({_candidates('s', starts)}, {_candidates('g', goals)}, "
            f"{int(max_transfers)}, Plans)")
    solution = next(iter(_prolog.query(goal, maxresult=1)), None)
    if solution is None:
        return []
    return [[(str(code), int(board), int(alight), int(ride), int(walk))
             for code, board, alight, ride, walk in plan]
            for plan in solution["Plans"]]


def best_trips(starts: Sequence[tuple[str, int, int]], goals: Sequence[tuple[str, int, int]],
               max_transfers: int) -> list[list[tuple]]:
    """The best plan per sequence of routes.

    starts/goals are (route_code, position_m, walk_m). Each plan is a list of
    (route_code, board_m, alight_m, ride_m, walk_to_next_m).
    """
    if not starts or not goals:
        return []
    return _run(_best, starts, goals, max_transfers)
