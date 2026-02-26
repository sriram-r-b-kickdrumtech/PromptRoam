"""
TSP with hard time windows (Phase 10). Nearest-neighbor heuristic: order waypoints
so that each next stop is feasible for time window and minimizes travel cost.

Waypoints have: id, lat, lon, time_window_start, time_window_end (optional).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class TSPInput:
    """One waypoint with optional time window (minutes from day start or absolute)."""
    id: str
    lat: float
    lon: float
    time_window_start: float | None = None  # minutes from midnight or absolute
    time_window_end: float | None = None
    label: str | None = None


@dataclass
class TSPResult:
    """Ordered sequence of waypoint ids that respects time windows."""
    ordered_ids: list[str]
    total_cost: float  # sum of straight-line distances for MVP
    feasible: bool


def _dist(a: TSPInput, b: TSPInput) -> float:
    """Euclidean distance (simplified; use proper haversine in production)."""
    return ((a.lat - b.lat) ** 2 + (a.lon - b.lon) ** 2) ** 0.5


def order_waypoints_with_time_windows(
    waypoints: list[TSPInput],
    start_id: str | None = None,
) -> TSPResult:
    """
    Nearest-neighbor with time-window feasibility. Start at start_id or first.
    Returns ordered_ids and feasible=True if all windows respected.
    """
    log.debug("[TSP] entry waypoints=%s start_id=%s", len(waypoints), start_id)

    if not waypoints:
        return TSPResult(ordered_ids=[], total_cost=0.0, feasible=True)

    by_id = {w.id: w for w in waypoints}
    if start_id and start_id in by_id:
        current = by_id[start_id]
        remaining = [w for w in waypoints if w.id != start_id]
    else:
        current = waypoints[0]
        remaining = waypoints[1:]

    ordered = [current.id]
    total_cost = 0.0
    current_time = current.time_window_start or 0.0

    while remaining:
        best: TSPInput | None = None
        best_dist = float("inf")
        for w in remaining:
            d = _dist(current, w)
            # Feasibility: arrival at current_time + travel must be <= time_window_end if set
            arrival = current_time + d  # simplistic: treat dist as minutes for MVP
            if w.time_window_end is not None and arrival > w.time_window_end:
                continue
            if w.time_window_start is not None and arrival < w.time_window_start:
                arrival = w.time_window_start
            if d < best_dist:
                best_dist = d
                best = w
        if best is None:
            # No feasible next; pick nearest anyway and mark infeasible
            best = min(remaining, key=lambda w: _dist(current, w))
            best_dist = _dist(current, best)
            feasible_this = False
        else:
            feasible_this = True

        total_cost += best_dist
        current_time = current_time + best_dist
        if best.time_window_start is not None and current_time < best.time_window_start:
            current_time = best.time_window_start
        ordered.append(best.id)
        current = best
        remaining = [w for w in remaining if w.id != best.id]

    # Final feasibility: all windows respected
    feasible = True
    t = waypoints[0].time_window_start or 0.0
    for i, wid in enumerate(ordered):
        w = by_id[wid]
        if w.time_window_end is not None and t > w.time_window_end:
            feasible = False
            break
        if i + 1 < len(ordered):
            next_w = by_id[ordered[i + 1]]
            t += _dist(w, next_w)
    log.debug("[TSP] exit ordered=%s total_cost=%.2f feasible=%s", ordered, total_cost, feasible)
    return TSPResult(ordered_ids=ordered, total_cost=total_cost, feasible=feasible)
