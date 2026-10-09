"""Level 1 — Confirmed flags, straight from recorded PFF/plays data, no
modeling (Requirement 5). Level 1 is the answer key Level 2 and Level 3 are
calibrated against.
"""
from __future__ import annotations

import polars as pl

from pipeline.config import REPO_ROOT
from pipeline.detect.flag import clamp_to_play, flags_to_dataframe, new_flag

PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def _last_frame_ids(tracking_norm: pl.DataFrame) -> pl.DataFrame:
    return tracking_norm.group_by(["gameId", "playId"]).agg(lastFrameId=pl.col("frameId").max())


def _player_team(tracking_norm: pl.DataFrame) -> pl.DataFrame:
    return (
        tracking_norm.filter(~pl.col("isBall"))
        .select("gameId", "playId", "nflId", "team")
        .unique()
    )


def detect_penalties(plays: pl.DataFrame, bounds: pl.DataFrame, player_team: pl.DataFrame) -> list[dict]:
    flags = []
    for suffix in ("1", "2", "3"):
        name_col, id_col = f"foulName{suffix}", f"foulNFLId{suffix}"
        rows = plays.filter(pl.col(id_col).is_not_null()).select(
            "gameId", "playId", "snapFrameId", pl.col(name_col).alias("foulName"),
            pl.col(id_col).cast(pl.Int64).alias("nflId"),
        )
        for row in rows.iter_rows(named=True):
            team_row = player_team.filter(
                (pl.col("gameId") == row["gameId"]) & (pl.col("playId") == row["playId"]) & (pl.col("nflId") == row["nflId"])
            )
            team = team_row["team"][0] if team_row.height else "UNK"
            last = bounds.filter((pl.col("gameId") == row["gameId"]) & (pl.col("playId") == row["playId"]))
            last_frame = int(last["lastFrameId"][0]) if last.height else row["snapFrameId"]
            error_frame = clamp_to_play(row["snapFrameId"], row["snapFrameId"], last_frame)
            flags.append(
                new_flag(
                    game_id=row["gameId"], play_id=row["playId"], error_frame_id=error_frame,
                    involved_nfl_ids=[int(row["nflId"])], team=team, error_type="penalty",
                    confidence_level="Confirmed",
                    explanation=f"{row['foulName']} charged at the snap.",
                    detail={"source": "penalty", "label": row["foulName"]},
                )
            )
    return flags


def detect_allowed_pressure(
    pff: pl.DataFrame,
    engagements: pl.DataFrame,
    player_measurements: pl.DataFrame,
    plays_resolved: pl.DataFrame,
    bounds: pl.DataFrame,
) -> list[dict]:
    """pff_sackAllowed | pff_hitAllowed | pff_hurryAllowed == 1 (Req 5.2)."""
    labels = [("pff_sackAllowed", "sack_allowed", "allowed a sack"),
              ("pff_hitAllowed", "hit_allowed", "allowed a hit on the QB"),
              ("pff_hurryAllowed", "hurry_allowed", "allowed a hurry on the QB")]

    # engaged (or pff_nflIdBlockedPlayer) rusher's closest-approach frame
    closest = player_measurements.select(
        "gameId", "playId", pl.col("nflId").alias("rusherNflId"), "closestApproachFrameId"
    )
    primary_engagement = (
        engagements.sort("minDistance")
        .group_by(["gameId", "playId", "blockerNflId"])
        .agg(rusherNflId=pl.col("rusherNflId").first())
    )

    plays_meta = plays_resolved.select("gameId", "playId", "snapFrameId", pl.col("possessionTeam").alias("offense"))
    bounds_m = bounds

    flags = []
    for col, error_type, verb in labels:
        rows = pff.filter(pl.col(col) == 1).select(
            "gameId", "playId", pl.col("nflId").alias("blockerNflId"), "pff_nflIdBlockedPlayer"
        )
        rows = rows.join(primary_engagement, on=["gameId", "playId", "blockerNflId"], how="left")
        rows = rows.with_columns(
            rusherNflId=pl.coalesce(["pff_nflIdBlockedPlayer", "rusherNflId"])
        )
        rows = rows.join(closest, on=["gameId", "playId", "rusherNflId"], how="left")
        rows = rows.join(plays_meta, on=["gameId", "playId"], how="left")
        rows = rows.join(bounds_m, on=["gameId", "playId"], how="left")

        for row in rows.iter_rows(named=True):
            if row["snapFrameId"] is None:
                continue  # unresolved play, excluded from detection
            error_frame = row["closestApproachFrameId"]
            if error_frame is None:
                error_frame = row["snapFrameId"]
            error_frame = clamp_to_play(int(error_frame), int(row["snapFrameId"]), int(row["lastFrameId"]))
            involved = [int(row["blockerNflId"])]
            if row["rusherNflId"] is not None:
                involved.append(int(row["rusherNflId"]))
            flags.append(
                new_flag(
                    game_id=row["gameId"], play_id=row["playId"], error_frame_id=error_frame,
                    involved_nfl_ids=involved, team=row["offense"] or "UNK", error_type=error_type,
                    confidence_level="Confirmed",
                    explanation=f"Blocker {verb} at the rusher's closest approach to the QB.",
                    detail={"source": "pff", "label": col},
                )
            )
    return flags


def detect_beaten(
    pff: pl.DataFrame,
    engagements: pl.DataFrame,
    player_measurements: pl.DataFrame,
    plays_resolved: pl.DataFrame,
    bounds: pl.DataFrame,
) -> list[dict]:
    """pff_beatenByDefender == 1 (Req 5.3, 5.4): errorFrameId = frame the
    rusher passes the blocker (engagement end frame), falling back to the
    rusher's closest-approach frame when that cannot be determined."""
    closest = player_measurements.select(
        "gameId", "playId", pl.col("nflId").alias("rusherNflId"), "closestApproachFrameId"
    )
    primary_engagement = (
        engagements.sort("minDistance")
        .group_by(["gameId", "playId", "blockerNflId"])
        .agg(rusherNflId=pl.col("rusherNflId").first(), passFrameId=pl.col("endFrameId").first())
    )
    plays_meta = plays_resolved.select("gameId", "playId", "snapFrameId", pl.col("possessionTeam").alias("offense"))

    rows = pff.filter(pl.col("pff_beatenByDefender") == 1).select(
        "gameId", "playId", pl.col("nflId").alias("blockerNflId"), "pff_nflIdBlockedPlayer"
    )
    rows = rows.join(primary_engagement, on=["gameId", "playId", "blockerNflId"], how="left")
    rows = rows.with_columns(
        rusherNflId=pl.coalesce(["pff_nflIdBlockedPlayer", "rusherNflId"])
    )
    rows = rows.join(closest, on=["gameId", "playId", "rusherNflId"], how="left")
    rows = rows.join(plays_meta, on=["gameId", "playId"], how="left")
    rows = rows.join(bounds, on=["gameId", "playId"], how="left")

    flags = []
    for row in rows.iter_rows(named=True):
        if row["snapFrameId"] is None:
            continue
        error_frame = row["passFrameId"] if row["passFrameId"] is not None else row["closestApproachFrameId"]
        if error_frame is None:
            error_frame = row["snapFrameId"]
        error_frame = clamp_to_play(int(error_frame), int(row["snapFrameId"]), int(row["lastFrameId"]))
        involved = [int(row["blockerNflId"])]
        if row["rusherNflId"] is not None:
            involved.append(int(row["rusherNflId"]))
        flags.append(
            new_flag(
                game_id=row["gameId"], play_id=row["playId"], error_frame_id=error_frame,
                involved_nfl_ids=involved, team=row["offense"] or "UNK", error_type="beaten_by_defender",
                confidence_level="Confirmed",
                explanation="Blocker was beaten by the rusher he was assigned to.",
                detail={"source": "pff", "label": "pff_beatenByDefender"},
            )
        )
    return flags


def main() -> None:
    plays = pl.read_parquet(PROCESSED_DIR / "plays.parquet")
    resolution = pl.read_parquet(PROCESSED_DIR / "play_resolution.parquet")
    plays_resolved = plays.join(resolution, on=["gameId", "playId"], how="inner").filter(pl.col("resolved"))

    pff = pl.read_parquet(PROCESSED_DIR / "pff_scouting.parquet")
    engagements = pl.read_parquet(PROCESSED_DIR / "engagements.parquet")
    player_measurements = pl.read_parquet(PROCESSED_DIR / "player_measurements.parquet")
    tracking_norm = pl.read_parquet(PROCESSED_DIR / "tracking_norm.parquet")

    bounds = _last_frame_ids(tracking_norm)
    player_team = _player_team(tracking_norm)

    all_flags = []
    all_flags += detect_penalties(plays_resolved, bounds, player_team)
    all_flags += detect_allowed_pressure(pff, engagements, player_measurements, plays_resolved, bounds)
    all_flags += detect_beaten(pff, engagements, player_measurements, plays_resolved, bounds)

    flags_df = flags_to_dataframe(all_flags)
    flags_df.write_parquet(PROCESSED_DIR / "flags_level1.parquet")
    print(f"Wrote flags_level1.parquet ({flags_df.height} Confirmed flags)")


if __name__ == "__main__":
    main()
