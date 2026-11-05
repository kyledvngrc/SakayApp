"""Python <-> SWI-Prolog bridge.                           (IMPERATIVE PARADIGM)

pyswip is not safe to call from several threads at once, so every Prolog call
runs on one dedicated worker thread. Callers block until their call finishes.

Path finding itself stays in prolog/routes.pl; this module only loads facts and
runs queries.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable, Sequence

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prolog")
_prolog: Any = None
MAX_SOLUTIONS = 5000            # safety cap on backtracking results per query
_SAFE_CODE = re.compile(r"^[A-Za-z0-9_-]+$")


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


def _load_legs(legs: list[tuple[str, int, int]]) -> int:
    list(_prolog.query("routes:clear_legs"))
    count = 0
    for code, from_stop, to_stop in legs:
        _prolog.assertz(f"routes:leg({quote_atom(code)}, {int(from_stop)}, {int(to_stop)})")
        count += 1
    return count


def load_legs(legs: Iterable[tuple[str, int, int]]) -> int:
    """Replace all leg/3 facts. Returns the number of facts asserted."""
    return _run(_load_legs, list(legs))


def _int_list(values: Sequence[int]) -> str:
    return "[" + ",".join(str(int(v)) for v in values) + "]"


def _find(starts: Sequence[int], ends: Sequence[int], max_transfers: int) -> list[list[tuple]]:
    goal = (f"routes:find_trips_rows({_int_list(starts)}, {_int_list(ends)}, "
            f"{int(max_transfers)}, Rows, _)")
    plans = []
    for solution in _prolog.query(goal, maxresult=MAX_SOLUTIONS):
        plans.append([(str(code), int(board), int(alight), tuple(int(s) for s in stops))
                      for code, board, alight, stops in solution["Rows"]])
    return plans


def find_trips(starts: Sequence[int], ends: Sequence[int], max_transfers: int) -> list[list[tuple]]:
    """Every plan between any start stop and any end stop.

    Each plan is a list of (route_code, board_stop, alight_stop, stop_ids).
    """
    if not starts or not ends:
        return []
    return _run(_find, starts, ends, max_transfers)
