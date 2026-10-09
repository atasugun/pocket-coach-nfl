"""Level 2 — Likely flags, explicit rule-based detection (Requirement 6).
Each rule reads its thresholds from config/thresholds.yaml and labels every
flag "Likely: check the film". Calibrated against Level 1 as the answer key
(see calibrate.py).
"""
from __future__ import annotations

import polars as pl

from pipeline.config import REPO_ROOT, Thresholds, load_thresholds
from pipeline.detect.flag import clamp_to_play, flags_to_dataframe, new_flag
from pipeline.features import EDGE_POSITIONS, _dropback_frame, _windowed_tracking

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
LABEL = "Likely: check the film"


def countable_blocker_count(pff: pl.DataFrame, excluded_block_types: tuple[str, ...]) -> pl.DataFrame:
    """Requirement 6.6: count only pass blockers whose block type is not
    CH, SR, or NB."""
    blockers = pff.filter(pl.col("pff_role") == "Pass Block")
    countable = blockers.filter(
        ~pl.col("pff_blockType").is_in(list(excluded_block_types)) | pl.col("pff_blockType").is_null()
    )
    return countable.group_by(["gameId", "playId"]).agg(countableBlockerCount=pl.col("nflId").n_unique())


# ---------------------------------------------------------------------------
# Rule 1 — Free rusher (6.1)
# ---------------------------------------------------------------------------


def detect_free_rusher(
    plays_resolved: pl.DataFrame,
    player_measurements: pl.DataFrame,
    play_features: pl.DataFrame,
    blocker_counts: pl.DataFrame,
    window: pl.DataFrame,
    thresholds: Thresholds,
) -> list[dict]:
    rushers = player_measurements.filter(pl.col("timeToPressure").is_not_null() & ~pl.col("hadEngagement"))
    rushers = rushers.join(play_features.select("gameId", "playId", "rusherCount"), on=["gameId", "playId"])
    rushers = rushers.join(blocker_counts, on=["gameId", "playId"], how="left")
    rushers = rushers.filter(pl.col("countableBlockerCount").fill_null(0) >= pl.col("rusherCount"))
    rushers = rushers.join(
        plays_resolved.select("gameId", "playId", "snapFrameId", pl.col("possessionTeam").alias("offense")),
        on=["gameId", "playId"],
    )
    bounds = window.group_by(["gameId", "playId"]).agg(lastFrameId=pl.col("frameId").max())
    rushers = rushers.join(bounds, on=["gameId", "playId"], how="left")
    rushers = rushers.with_columns(
        rawFrame=(pl.col("snapFrameId") + (pl.col("timeToPressure") * 10).round(0)).cast(pl.Int64)
    )

    blockers_at_frame = window.filter(pl.col("pff_role") == "Pass Block").select(
        "gameId", "playId", "frameId", pl.col("nflId").alias("blockerNflId"), pl.col("x").alias("bx"), pl.col("y").alias("by")
    )

    flags = []
    for row in rushers.iter_rows(named=True):
        last_frame = row["lastFrameId"] or row["rawFrame"]
        error_frame = clamp_to_play(int(row["rawFrame"]), int(row["snapFrameId"]), int(last_frame))
        nearest = blockers_at_frame.filter(
            (pl.col("gameId") == row["gameId"]) & (pl.col("playId") == row["playId"]) & (pl.col("frameId") == error_frame)
        )
        involved = [int(row["nflId"])]
        if nearest.height:
            involved.append(int(nearest.sort("bx")["blockerNflId"][0]))
        flags.append(
            new_flag(
                game_id=row["gameId"], play_id=row["playId"], error_frame_id=error_frame,
                involved_nfl_ids=involved, team=row["offense"] or "UNK", error_type="free_rusher",
                confidence_level="Likely",
                explanation=f"{LABEL}: a rusher reached the QB with no blocker ever engaged.",
                detail={"rule": "free_rusher"},
            )
        )
    return flags


# ---------------------------------------------------------------------------
# Rule 2 — Wasted double team (6.2)
# ---------------------------------------------------------------------------


def detect_wasted_double_team(
    engagements: pl.DataFrame, player_measurements: pl.DataFrame, plays_resolved: pl.DataFrame
) -> list[dict]:
    double_teamed = (
        engagements.group_by(["gameId", "playId", "rusherNflId"])
        .agg(blockerNflIds=pl.col("blockerNflId").unique(), starts=pl.col("startFrameId"))
        .filter(pl.col("blockerNflIds").list.len() >= 2)
    )
    # closestApproachDist is only ever populated for rusher rows, so this
    # also excludes blocker rows (which all carry hadEngagement=False by
    # construction in features.py and would otherwise look "free").
    free_rushers = (
        player_measurements.filter(~pl.col("hadEngagement") & pl.col("closestApproachDist").is_not_null())
        .select("gameId", "playId", pl.col("nflId").alias("freeRusherNflId"))
    )
    plays_with_free = free_rushers.select("gameId", "playId").unique()
    double_teamed = double_teamed.join(plays_with_free, on=["gameId", "playId"], how="inner")

    plays_meta = plays_resolved.select("gameId", "playId", pl.col("possessionTeam").alias("offense"))

    flags = []
    for row in double_teamed.iter_rows(named=True):
        blocker_ids = sorted(row["blockerNflIds"])[:2]
        error_frame = max(row["starts"]) if row["starts"] else None
        if error_frame is None:
            continue
        free = free_rushers.filter(
            (pl.col("gameId") == row["gameId"]) & (pl.col("playId") == row["playId"])
        )
        free_id = int(free["freeRusherNflId"][0]) if free.height else None
        offense_row = plays_meta.filter((pl.col("gameId") == row["gameId"]) & (pl.col("playId") == row["playId"]))
        offense = offense_row["offense"][0] if offense_row.height else "UNK"
        involved = [int(b) for b in blocker_ids] + ([free_id] if free_id else [])
        flags.append(
            new_flag(
                game_id=row["gameId"], play_id=row["playId"], error_frame_id=int(error_frame),
                involved_nfl_ids=involved, team=offense, error_type="wasted_double_team",
                confidence_level="Likely",
                explanation=f"{LABEL}: two blockers doubled one rusher while another rusher went unblocked.",
                detail={"rule": "wasted_double_team", "rusherNflId": int(row["rusherNflId"])},
            )
        )
    return flags


# ---------------------------------------------------------------------------
# Rule 3 — Stunt not handled (6.3)
# ---------------------------------------------------------------------------


def find_crossing_pairs(window: pl.DataFrame, stunt_window_s: float) -> pl.DataFrame:
    """For each play, find rusher pairs whose lateral (y) order flips
    within `stunt_window_s` of the snap — the frame-level signature of two
    rushers exchanging gaps (a stunt/cross)."""
    rushers = window.filter(pl.col("pff_role") == "Pass Rush").select(
        "gameId", "playId", "frameId", "nflId", "y", "snapFrameId"
    ).with_columns(elapsed=(pl.col("frameId") - pl.col("snapFrameId")) / 10.0).filter(
        pl.col("elapsed") <= stunt_window_s
    )

    rows = []
    for (game_id, play_id), g in rushers.group_by(["gameId", "playId"], maintain_order=True):
        ids = sorted(g["nflId"].unique().to_list())
        if len(ids) < 2:
            continue
        by_id = {i: g.filter(pl.col("nflId") == i).sort("frameId") for i in ids}
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = by_id[ids[i]], by_id[ids[j]]
                merged = a.join(b, on="frameId", suffix="_b").sort("frameId")
                if merged.height < 2:
                    continue
                ys_a = merged["y"].to_list()
                ys_b = merged["y_b"].to_list()
                frames = merged["frameId"].to_list()
                prev_sign = None
                for f, ya, yb in zip(frames, ys_a, ys_b):
                    sign = (ya - yb) > 0
                    if prev_sign is not None and sign != prev_sign:
                        rows.append(
                            {"gameId": game_id, "playId": play_id, "rusherA": ids[i], "rusherB": ids[j], "crossFrameId": f}
                        )
                        break
                    prev_sign = sign
    if not rows:
        return pl.DataFrame(
            schema={"gameId": pl.Int64, "playId": pl.Int64, "rusherA": pl.Int64, "rusherB": pl.Int64, "crossFrameId": pl.Int64}
        )
    return pl.DataFrame(rows)


def detect_stunt_not_handled(
    window: pl.DataFrame,
    pff: pl.DataFrame,
    engagements: pl.DataFrame,
    player_measurements: pl.DataFrame,
    plays_resolved: pl.DataFrame,
    stunt_window_s: float,
) -> list[dict]:
    crossings = find_crossing_pairs(window, stunt_window_s)
    if crossings.height == 0:
        return []

    sw_blockers = pff.filter(pl.col("pff_blockType") == "SW").select("gameId", "playId", pl.col("nflId").alias("swBlockerId"))
    sw_plays = sw_blockers.select("gameId", "playId").unique().with_columns(hasSW=pl.lit(True))
    crossings = crossings.join(sw_plays, on=["gameId", "playId"], how="left")
    crossings = crossings.filter(pl.col("hasSW").is_null())  # no SW recorded anywhere on the play

    pm = player_measurements.select(
        "gameId", "playId", pl.col("nflId"), "hadEngagement",
    )
    pressure_rushers = pff.filter((pl.col("pff_hit") == 1) | (pl.col("pff_hurry") == 1) | (pl.col("pff_sack") == 1)).select(
        "gameId", "playId", pl.col("nflId").alias("pressureNflId")
    )

    plays_meta = plays_resolved.select("gameId", "playId", pl.col("defensiveTeam").alias("defense"))

    flags = []
    for row in crossings.iter_rows(named=True):
        a_meas = pm.filter(
            (pl.col("gameId") == row["gameId"]) & (pl.col("playId") == row["playId"]) & (pl.col("nflId") == row["rusherA"])
        )
        b_meas = pm.filter(
            (pl.col("gameId") == row["gameId"]) & (pl.col("playId") == row["playId"]) & (pl.col("nflId") == row["rusherB"])
        )
        a_free = a_meas.height == 0 or not a_meas["hadEngagement"][0]
        b_free = b_meas.height == 0 or not b_meas["hadEngagement"][0]
        pressure = pressure_rushers.filter(
            (pl.col("gameId") == row["gameId"]) & (pl.col("playId") == row["playId"])
            & pl.col("pressureNflId").is_in([row["rusherA"], row["rusherB"]])
        ).height > 0
        if not (a_free or b_free or pressure):
            continue
        offense_row = plays_meta.filter((pl.col("gameId") == row["gameId"]) & (pl.col("playId") == row["playId"]))
        defense = offense_row["defense"][0] if offense_row.height else "UNK"
        flags.append(
            new_flag(
                game_id=row["gameId"], play_id=row["playId"], error_frame_id=int(row["crossFrameId"]),
                involved_nfl_ids=[int(row["rusherA"]), int(row["rusherB"])],
                team=defense, error_type="stunt_not_handled",
                confidence_level="Likely",
                explanation=f"{LABEL}: a twist/stunt crossed two rushers' paths and the protection did not pass them off.",
                detail={"rule": "stunt_not_handled"},
            )
        )
    return flags


# ---------------------------------------------------------------------------
# Rule 4 — Lost escape lane (6.4)
# ---------------------------------------------------------------------------


def detect_lost_escape_lane(
    window: pl.DataFrame, plays_resolved: pl.DataFrame, pff: pl.DataFrame
) -> list[dict]:
    scrambles = plays_resolved.filter(pl.col("passResult") == "R")
    if scrambles.height == 0:
        return []

    edge = pff.filter(pl.col("pff_positionLinedUp").is_in(list(EDGE_POSITIONS))).select(
        "gameId", "playId", pl.col("nflId").alias("edgeNflId")
    )

    plays_meta = scrambles.select("gameId", "playId", "snapFrameId", pl.col("defensiveTeam").alias("defense"))
    win = window.join(plays_meta.select("gameId", "playId"), on=["gameId", "playId"], how="inner")

    tackle_box = (
        win.filter(pl.col("pff_role") == "Pass Block")
        .filter(pl.col("frameId") == pl.col("snapFrameId"))
        .group_by(["gameId", "playId"])
        .agg(centerY=pl.col("y").mean(), halfWidth=((pl.col("y").max() - pl.col("y").min()) / 2).clip(2.0, None))
    )

    qb = win.filter(pl.col("pff_role") == "Pass").select("gameId", "playId", "frameId", pl.col("y").alias("qby"))
    qb = qb.join(tackle_box, on=["gameId", "playId"])
    qb = qb.with_columns(outside=((pl.col("qby") - pl.col("centerY")).abs() > pl.col("halfWidth")))
    exit_frame = (
        qb.filter(pl.col("outside"))
        .group_by(["gameId", "playId"])
        .agg(exitFrameId=pl.col("frameId").min())
    )

    flags = []
    for row in exit_frame.iter_rows(named=True):
        game_id, play_id, exit_frame_id = row["gameId"], row["playId"], row["exitFrameId"]
        qb_row = qb.filter(
            (pl.col("gameId") == game_id) & (pl.col("playId") == play_id) & (pl.col("frameId") == exit_frame_id)
        )
        if qb_row.height == 0:
            continue
        qby, center_y = qb_row["qby"][0], qb_row["centerY"][0]
        qb_spread = abs(qby - center_y)
        edge_ids = edge.filter((pl.col("gameId") == game_id) & (pl.col("playId") == play_id))["edgeNflId"].to_list()
        if len(edge_ids) < 2:
            continue
        positions = win.filter(
            (pl.col("gameId") == game_id) & (pl.col("playId") == play_id)
            & (pl.col("frameId") == exit_frame_id) & pl.col("nflId").is_in(edge_ids)
        )
        if positions.height < 2:
            continue
        # "Inside the QB": both edge defenders sit closer to the formation
        # center (laterally) than the QB does once he has broken outside
        # the box — i.e. neither edge rusher is still outside him
        # containing the escape lane, regardless of which side each lines
        # up on.
        inside_flags = [abs(r["y"] - center_y) < qb_spread for r in positions.iter_rows(named=True)]
        if all(inside_flags):
            defense = plays_meta.filter((pl.col("gameId") == game_id) & (pl.col("playId") == play_id))["defense"][0]
            flags.append(
                new_flag(
                    game_id=game_id, play_id=play_id, error_frame_id=int(exit_frame_id),
                    involved_nfl_ids=[int(i) for i in edge_ids[:2]], team=defense, error_type="lost_escape_lane",
                    confidence_level="Likely",
                    explanation=f"{LABEL}: both edge rushers were inside the QB when he broke outside the tackle box.",
                    detail={"rule": "lost_escape_lane"},
                )
            )
    return flags


def main() -> None:
    thresholds = load_thresholds()
    tracking_norm = pl.read_parquet(PROCESSED_DIR / "tracking_norm.parquet")
    pff = pl.read_parquet(PROCESSED_DIR / "pff_scouting.parquet")
    engagements = pl.read_parquet(PROCESSED_DIR / "engagements.parquet")
    player_measurements = pl.read_parquet(PROCESSED_DIR / "player_measurements.parquet")
    play_features = pl.read_parquet(PROCESSED_DIR / "play_features.parquet")

    plays_resolved = _dropback_frame()
    window = _windowed_tracking(tracking_norm, plays_resolved)
    blocker_counts = countable_blocker_count(pff, thresholds.level2.excluded_block_types)

    all_flags = []
    all_flags += detect_free_rusher(plays_resolved, player_measurements, play_features, blocker_counts, window, thresholds)
    all_flags += detect_wasted_double_team(engagements, player_measurements, plays_resolved)
    all_flags += detect_stunt_not_handled(window, pff, engagements, player_measurements, plays_resolved, thresholds.level2.stunt_window_s)
    all_flags += detect_lost_escape_lane(window, plays_resolved, pff)

    flags_df = flags_to_dataframe(all_flags)
    flags_df.write_parquet(PROCESSED_DIR / "flags_level2.parquet")
    print(f"Wrote flags_level2.parquet ({flags_df.height} Likely flags)")


if __name__ == "__main__":
    main()
