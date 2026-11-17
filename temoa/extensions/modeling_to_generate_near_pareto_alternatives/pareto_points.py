"""
Selection of the Pareto optimal solutions around which an MGPA run explores alternatives
"""

from __future__ import annotations

from logging import getLogger
from typing import Any

logger = getLogger(__name__)

ALL_POINTS = 'all'
ELBOW_POINT = 'elbow'


def elbow_point(front: dict[int, tuple[float, float]]) -> int:
    """
    Return the index of the elbow of a Pareto front given as {index: (f1, f2)}:  the point farthest
    from the line joining the two ends of the front, on the side of the lower objective values,
    after scaling both objectives by their range over the front.
    """
    if not front:
        raise ValueError('Cannot locate the elbow of an empty Pareto front')
    indices = sorted(front, key=lambda n: front[n][1])
    first, last = indices[0], indices[-1]
    f1_range = front[first][0] - front[last][0]
    f2_range = front[last][1] - front[first][1]
    if len(indices) < 3 or f1_range <= 0 or f2_range <= 0:
        logger.warning(
            'The Pareto front has no elbow (fewer than 3 points, or a single solution).  '
            'Using solution %d.',
            first,
        )
        return first
    distances = {
        n: 1.0
        - (front[n][0] - front[last][0]) / f1_range
        - (front[n][1] - front[first][1]) / f2_range
        for n in indices
    }
    return max(indices, key=lambda n: distances[n])


def parse_points(raw: object) -> str | list[int]:
    """Parse the MGPA option "points":  "all", "elbow" or a list of Pareto solution indices"""
    if isinstance(raw, str):
        label = raw.strip().lower()
        if label in (ALL_POINTS, ELBOW_POINT):
            return label
    elif isinstance(raw, int) and not isinstance(raw, bool):
        return [raw]
    elif isinstance(raw, (list, tuple)) and all(
        isinstance(item, int) and not isinstance(item, bool) for item in raw
    ):
        return sorted(set(raw))
    raise ValueError(
        f'Invalid MGPA option points: {raw!r}.  Valid choices are "all", "elbow" or a list of '
        'Pareto solution indices'
    )


def parse_f2_values(raw: object) -> list[float]:
    """Parse the MGPA option "f2_values":  a value of f2, or a list of them"""
    if raw is None:
        return []
    items: list[Any] = list(raw) if isinstance(raw, (list, tuple)) else [raw]
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in items):
        raise ValueError(f'Invalid MGPA option f2_values: {raw!r}.  A list of numbers is expected')
    return [float(item) for item in items]


def select_points(points: str | list[int], front: dict[int, tuple[float, float]]) -> list[int]:
    """Return the indices of the Pareto solutions of the front to explore"""
    if isinstance(points, str):
        return [elbow_point(front)] if points == ELBOW_POINT else sorted(front)
    missing = [n for n in points if n not in front]
    if missing:
        raise ValueError(
            f'MGPA points {missing} are not solutions of the Pareto front.  '
            f'Available: {sorted(front)}'
        )
    return list(points)
