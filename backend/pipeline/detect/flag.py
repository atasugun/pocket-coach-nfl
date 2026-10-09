"""The canonical, stable Flag schema (Requirement 8.1, 16.4). Every
confidence level (Confirmed/Likely/Possible) emits rows conforming to this
schema so a future broadcaster mode can reuse detection outputs unchanged.

Per-type errorFrameId derivation (the schema contract):
  - penalty                      -> the snap frame
  - sack/hit/hurry allowed       -> the engaged (or pff_nflIdBlockedPlayer)
                                     rusher's closest-approach-to-QB frame
  - beatenByDefender              -> the frame the rusher passes the blocker,
                                     falling back to that rusher's
                                     closest-approach frame
"""
from __future__ import annotations

import hashlib
from typing import Any

import polars as pl

FLAG_SCHEMA = {
    "flagId": pl.Utf8,
    "gameId": pl.Int64,
    "playId": pl.Int64,
    "errorFrameId": pl.Int64,
    "involvedNflIds": pl.List(pl.Int64),
    "team": pl.Utf8,
    "errorType": pl.Utf8,
    "confidenceLevel": pl.Utf8,
    "explanation": pl.Utf8,
    "epaCost": pl.Float64,
    "detail": pl.Utf8,  # JSON-encoded, level-specific
}


def make_flag_id(
    game_id: int, play_id: int, error_type: str, involved_nfl_ids: list[int], error_frame_id: int, detail: dict[str, Any]
) -> str:
    """Deterministic flagId hash (Requirement 8.1). Includes errorFrameId
    and `detail` because the same players/errorType/frame can legitimately
    recur as genuinely distinct events on one play — e.g. two different
    penalties (holding and pass interference) on the same player at the
    snap, or the same two blockers double-teaming two different rushers in
    sequence — and `detail` is exactly what tells those apart."""
    import json as _json

    detail_key = _json.dumps(detail, sort_keys=True, default=str)
    key = f"{game_id}:{play_id}:{error_type}:{','.join(str(i) for i in sorted(involved_nfl_ids))}:{error_frame_id}:{detail_key}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def new_flag(
    game_id: int,
    play_id: int,
    error_frame_id: int,
    involved_nfl_ids: list[int],
    team: str,
    error_type: str,
    confidence_level: str,
    explanation: str,
    detail: dict[str, Any],
    epa_cost: float | None = None,
) -> dict:
    """Build one Flag row conforming to FLAG_SCHEMA. `errorFrameId` must
    satisfy snapFrameId <= errorFrameId <= lastFrameId for the play
    (Property 7) — callers are responsible for clamping before calling
    this, since this module has no access to the play's frame bounds."""
    import json

    return {
        "flagId": make_flag_id(game_id, play_id, error_type, involved_nfl_ids, error_frame_id, detail),
        "gameId": game_id,
        "playId": play_id,
        "errorFrameId": error_frame_id,
        "involvedNflIds": involved_nfl_ids,
        "team": team,
        "errorType": error_type,
        "confidenceLevel": confidence_level,
        "explanation": explanation,
        "epaCost": epa_cost,
        "detail": json.dumps(detail),
    }


def flags_to_dataframe(flags: list[dict]) -> pl.DataFrame:
    if not flags:
        return pl.DataFrame(schema=FLAG_SCHEMA)
    return pl.DataFrame(flags, schema=FLAG_SCHEMA)


def clamp_to_play(frame_id: int, snap_frame_id: int, last_frame_id: int) -> int:
    return max(snap_frame_id, min(frame_id, last_frame_id))
