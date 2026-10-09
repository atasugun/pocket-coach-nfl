"""Direction normalization, LOS, time-since-snap, PFF join, ball tagging
(Requirement 3). Writes `tracking_norm` and `play_features` (snap/end/LOS
only at this stage — the rest of play_features is filled in by features.py).
"""
from __future__ import annotations

import polars as pl

from pipeline.config import REPO_ROOT, load_thresholds
from pipeline.resolve import resolve_play_frames

PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def normalize_direction(tracking: pl.DataFrame, field_length: float, field_width: float) -> pl.DataFrame:
    """Left-play transform (Requirement 3.1): flip x, y, o, dir so offense
    always moves toward increasing x. Right-direction rows are unchanged."""
    is_left = pl.col("playDirection") == "left"
    return tracking.with_columns(
        x=pl.when(is_left).then(field_length - pl.col("x")).otherwise(pl.col("x")),
        y=pl.when(is_left).then(field_width - pl.col("y")).otherwise(pl.col("y")),
        o=pl.when(is_left).then((pl.col("o") + 180) % 360).otherwise(pl.col("o")),
        dir=pl.when(is_left).then((pl.col("dir") + 180) % 360).otherwise(pl.col("dir")),
    )


def tag_ball_rows(tracking: pl.DataFrame) -> pl.DataFrame:
    """Requirement 3.5: nflId NA -> isBall=true, team='football'."""
    is_ball = pl.col("nflId").is_null()
    return tracking.with_columns(
        isBall=is_ball,
        team=pl.when(is_ball).then(pl.lit("football")).otherwise(pl.col("team")),
    )


def resolve_all_plays(tracking: pl.DataFrame) -> pl.DataFrame:
    """Run the resolver per (gameId, playId); returns one row per play."""
    rows = []
    for (game_id, play_id), play_tracking in tracking.group_by(
        ["gameId", "playId"], maintain_order=True
    ):
        r = resolve_play_frames(play_tracking)
        rows.append(
            {
                "gameId": game_id,
                "playId": play_id,
                "snapFrameId": r.snap_frame_id,
                "endOfDropbackFrameId": r.end_of_dropback_frame_id,
                "resolved": r.resolved,
                "unresolvedReason": r.reason,
            }
        )
    return pl.DataFrame(
        rows,
        schema={
            "gameId": pl.Int64,
            "playId": pl.Int64,
            "snapFrameId": pl.Int64,
            "endOfDropbackFrameId": pl.Int64,
            "resolved": pl.Boolean,
            "unresolvedReason": pl.Utf8,
        },
    )


def add_time_since_snap(tracking: pl.DataFrame, resolved: pl.DataFrame, frame_rate_hz: int) -> pl.DataFrame:
    """Requirement 3.3: timeSinceSnap = (frameId - snapFrameId) / frame_rate_hz."""
    joined = tracking.join(
        resolved.select("gameId", "playId", "snapFrameId"), on=["gameId", "playId"], how="left"
    )
    return joined.with_columns(
        timeSinceSnap=(pl.col("frameId") - pl.col("snapFrameId")) / frame_rate_hz
    )


def compute_line_of_scrimmage(tracking_norm: pl.DataFrame) -> pl.DataFrame:
    """Requirement 3.2: LOS = normalized ball x at the snap frame."""
    snap_ball = tracking_norm.filter(
        pl.col("isBall") & (pl.col("frameId") == pl.col("snapFrameId"))
    )
    return snap_ball.select("gameId", "playId", pl.col("x").alias("lineOfScrimmage"))


def join_pff_roles(tracking: pl.DataFrame, pff: pl.DataFrame) -> pl.DataFrame:
    """Requirement 3.4: join pff_role and pff_positionLinedUp by (gameId, playId, nflId)."""
    pff_cols = pff.select("gameId", "playId", "nflId", "pff_role", "pff_positionLinedUp")
    return tracking.join(pff_cols, on=["gameId", "playId", "nflId"], how="left")


def main() -> None:
    thresholds = load_thresholds()
    tracking = pl.read_parquet(PROCESSED_DIR / "tracking.parquet")
    pff = pl.read_parquet(PROCESSED_DIR / "pff_scouting.parquet")

    tracking = normalize_direction(
        tracking, thresholds.field.length_yd, thresholds.field.width_yd
    )
    tracking = tag_ball_rows(tracking)

    resolved = resolve_all_plays(tracking)
    resolved.write_parquet(PROCESSED_DIR / "play_resolution.parquet")

    tracking = add_time_since_snap(tracking, resolved, thresholds.field.frame_rate_hz)
    tracking = join_pff_roles(tracking, pff)

    los = compute_line_of_scrimmage(tracking)

    tracking.write_parquet(PROCESSED_DIR / "tracking_norm.parquet")
    los.write_parquet(PROCESSED_DIR / "line_of_scrimmage.parquet")

    n_resolved = resolved.filter(pl.col("resolved")).height
    print(
        f"Wrote tracking_norm.parquet ({tracking.height} rows), "
        f"play_resolution.parquet ({n_resolved}/{resolved.height} resolved), "
        f"line_of_scrimmage.parquet ({los.height} plays)"
    )


if __name__ == "__main__":
    main()
