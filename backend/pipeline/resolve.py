"""The single resolver for a play's snap frame and end-of-dropback frame.

Every downstream measurement, detection rule, and model shares this one
definition (Requirements 2.2, 2.3). `resolve_play_frames` is pure: it takes
one play's tracking rows and returns the resolved frames or the reason it
could not resolve them.
"""
from __future__ import annotations

from dataclasses import dataclass

import polars as pl

# First match wins within each group (Requirement 2.2, 2.3).
SNAP_EVENTS_PRECEDENCE = ["ball_snap", "autoevent_ballsnap"]
END_EVENTS_PRECEDENCE = [
    "pass_forward",
    "autoevent_passforward",
    "qb_sack",
    "qb_strip_sack",
    "run",
]
# Any other recognized terminal event, used only if none of the above exist.
FALLBACK_TERMINAL_EVENTS = [
    "pass_outcome_caught",
    "pass_outcome_incomplete",
    "pass_tipped",
    "pass_arrived",
    "tackle",
    "out_of_bounds",
    "fumble",
    "penalty_flag",
]


@dataclass(frozen=True)
class ResolvedPlay:
    snap_frame_id: int | None
    end_of_dropback_frame_id: int | None
    resolved: bool
    reason: str | None


def _first_frame_for_events(play_tracking: pl.DataFrame, events: list[str]) -> int | None:
    """Earliest frameId at which any of `events` occurs, honoring list order
    only as a precedence filter — the search itself is over frameId so a
    manual event occurring anywhere beats an automatic one only when both
    are candidates; precedence is applied by trying each event name in turn
    and taking the first one that occurs anywhere in the play."""
    for event in events:
        hit = play_tracking.filter(pl.col("event") == event)
        if hit.height > 0:
            return int(hit["frameId"].min())
    return None


def resolve_play_frames(play_tracking: pl.DataFrame) -> ResolvedPlay:
    """Resolve the snap frame and end-of-dropback frame for one play.

    `play_tracking` must contain at least `frameId` and `event` for every
    tracking row of a single (gameId, playId).
    """
    snap_frame_id = _first_frame_for_events(play_tracking, SNAP_EVENTS_PRECEDENCE)
    if snap_frame_id is None:
        return ResolvedPlay(None, None, False, "no_snap_event")

    end_frame_id = _first_frame_for_events(play_tracking, END_EVENTS_PRECEDENCE)
    if end_frame_id is None:
        end_frame_id = _first_frame_for_events(play_tracking, FALLBACK_TERMINAL_EVENTS)
    if end_frame_id is None:
        return ResolvedPlay(snap_frame_id, None, False, "no_end_of_dropback_event")

    if end_frame_id < snap_frame_id:
        return ResolvedPlay(snap_frame_id, end_frame_id, False, "end_precedes_snap")

    return ResolvedPlay(snap_frame_id, end_frame_id, True, None)
