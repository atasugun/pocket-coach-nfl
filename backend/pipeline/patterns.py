"""Pattern Engine (Requirement 9): group flags into recurring patterns,
compute opportunities denominators, Wilson 90% intervals, and rank by
frequency x average cost.
"""
from __future__ import annotations

import polars as pl

from pipeline.config import REPO_ROOT, load_thresholds
from pipeline.wilson import wilson_interval

PROCESSED_DIR = REPO_ROOT / "data" / "processed"

# Error types attributed to the blocker's pass-block rep count (Requirement 9.2).
BLOCKER_ATTRIBUTED = {
    "sack_allowed", "hit_allowed", "hurry_allowed", "beaten_by_defender",
    "worse_than_expected_rep", "free_rusher", "wasted_double_team", "pressure_spike",
}


def _distance_band(yards_to_go: int, bands: tuple[int, ...]) -> str:
    short, medium = bands
    if yards_to_go <= short:
        return "short"
    if yards_to_go <= medium:
        return "medium"
    return "long"


def _field_zone(absolute_yardline: float | None) -> str:
    if absolute_yardline is None:
        return "unknown"
    if absolute_yardline < 40:
        return "own_territory"
    if absolute_yardline < 80:
        return "midfield"
    return "red_zone"


def _score_state(pre_snap_home: int, pre_snap_visitor: int, possession_team: str, home_team: str) -> str:
    offense_score = pre_snap_home if possession_team == home_team else pre_snap_visitor
    defense_score = pre_snap_visitor if possession_team == home_team else pre_snap_home
    diff = offense_score - defense_score
    if diff > 0:
        return "leading"
    if diff < 0:
        return "trailing"
    return "tied"


def build_situation_table(plays: pl.DataFrame, games: pl.DataFrame, bands: tuple[int, ...]) -> pl.DataFrame:
    merged = plays.join(games.select("gameId", "homeTeamAbbr"), on="gameId", how="left")
    merged = merged.with_columns(
        distanceBand=pl.col("yardsToGo").map_elements(lambda y: _distance_band(y, bands), return_dtype=pl.Utf8),
        fieldZone=pl.col("absoluteYardlineNumber").map_elements(_field_zone, return_dtype=pl.Utf8),
    )
    merged = merged.with_columns(
        scoreState=pl.struct(["preSnapHomeScore", "preSnapVisitorScore", "possessionTeam", "homeTeamAbbr"]).map_elements(
            lambda s: _score_state(s["preSnapHomeScore"], s["preSnapVisitorScore"], s["possessionTeam"], s["homeTeamAbbr"]),
            return_dtype=pl.Utf8,
        )
    )
    merged = merged.with_columns(
        situationKey=pl.concat_str(
            [pl.col("down").cast(pl.Utf8), pl.col("distanceBand"), pl.col("fieldZone"), pl.col("scoreState")], separator="|"
        )
    )
    return merged.select(
        "gameId", "playId", "down", "distanceBand", "fieldZone", "scoreState", "situationKey",
        "possessionTeam", "defensiveTeam",
    )


def _attributed_player(row_involved: list[int], row_team: str, offense: str) -> int | None:
    # First involved id belongs to the charged side by construction in each
    # detector (blocker first for offense errors, rusher/edge first for
    # defense errors); fall back to the first id either way.
    return row_involved[0] if row_involved else None


def _primary_blocker_reps(player_measurements: pl.DataFrame, situations: pl.DataFrame) -> pl.DataFrame:
    blockers = player_measurements.filter(pl.col("closestApproachDist").is_null())  # blocker-only rows
    blockers = blockers.join(situations, on=["gameId", "playId"], how="inner")
    return blockers.group_by(["nflId", "situationKey"]).agg(opportunities=pl.col("playId").len())


def _pass_rush_snaps(player_measurements: pl.DataFrame, situations: pl.DataFrame) -> pl.DataFrame:
    rushers = player_measurements.filter(pl.col("closestApproachDist").is_not_null())
    rushers = rushers.join(situations, on=["gameId", "playId"], how="inner")
    return rushers.group_by(["defensiveTeam", "situationKey"]).agg(opportunities=pl.col("playId").len())


def _stunts_faced(crossing_pairs: pl.DataFrame, situations: pl.DataFrame) -> pl.DataFrame:
    plays_with_stunt = crossing_pairs.select("gameId", "playId").unique()
    joined = plays_with_stunt.join(situations, on=["gameId", "playId"], how="inner")
    return joined.group_by(["defensiveTeam", "situationKey"]).agg(opportunities=pl.col("playId").len())


def build_patterns(
    flags: pl.DataFrame,
    situations: pl.DataFrame,
    player_measurements: pl.DataFrame,
    crossing_pairs: pl.DataFrame,
    min_opportunities: int,
    interval_confidence: float,
) -> pl.DataFrame:
    flags = flags.join(situations, on=["gameId", "playId"], how="inner")
    flags = flags.with_columns(
        nflId=pl.col("involvedNflIds").list.first(),
        offense=pl.when(pl.col("team") == pl.col("possessionTeam")).then(pl.lit("self")).otherwise(pl.lit("opponent")),
        perspective=pl.when(pl.col("team") == pl.col("possessionTeam")).then(pl.lit("self")).otherwise(pl.lit("opponent")),
    )

    counts = flags.group_by(["team", "nflId", "errorType", "situationKey", "perspective"]).agg(
        count=pl.col("flagId").len(),
        avgCost=pl.col("epaCost").mean(),
        anyCost=pl.col("epaCost").is_not_null().any(),
        playRefs=pl.concat_list([pl.col("gameId"), pl.col("playId")]),
    )

    blocker_reps = _primary_blocker_reps(player_measurements, situations)
    rush_snaps = _pass_rush_snaps(player_measurements, situations)
    stunts = _stunts_faced(crossing_pairs, situations)

    is_lost_escape_lane = pl.col("errorType") == "lost_escape_lane"
    is_stunt = pl.col("errorType") == "stunt_not_handled"

    with_blocker_opp = counts.join(
        blocker_reps.rename({"nflId": "nflId_b"}), left_on=["nflId", "situationKey"], right_on=["nflId_b", "situationKey"], how="left"
    )
    with_blocker_opp = with_blocker_opp.join(
        rush_snaps.rename({"defensiveTeam": "team", "opportunities": "oppTeamSnaps"}), on=["team", "situationKey"], how="left"
    )
    with_blocker_opp = with_blocker_opp.join(
        stunts.rename({"defensiveTeam": "team", "opportunities": "oppStunts"}), on=["team", "situationKey"], how="left"
    )

    with_blocker_opp = with_blocker_opp.with_columns(
        opportunities=pl.when(is_lost_escape_lane)
        .then(pl.col("oppTeamSnaps"))
        .when(is_stunt)
        .then(pl.col("oppStunts"))
        .otherwise(pl.col("opportunities"))
    )
    with_blocker_opp = with_blocker_opp.with_columns(
        opportunities=pl.col("opportunities").fill_null(0),
        sampleSize=pl.col("opportunities").fill_null(0),
    )
    with_blocker_opp = with_blocker_opp.filter(pl.col("opportunities") >= min_opportunities)

    with_blocker_opp = with_blocker_opp.with_columns(
        rate=pl.col("count") / pl.col("opportunities")
    )

    base_cols = [c for c in with_blocker_opp.columns if c not in ("oppTeamSnaps", "oppStunts")]
    if with_blocker_opp.height == 0:
        result = with_blocker_opp.select(base_cols).with_columns(
            rateLow90=pl.lit(None, dtype=pl.Float64), rateHigh90=pl.lit(None, dtype=pl.Float64)
        )
    else:
        rows = []
        for row in with_blocker_opp.iter_rows(named=True):
            low, high = wilson_interval(row["count"], row["opportunities"], interval_confidence)
            rows.append({k: v for k, v in row.items() if k in base_cols} | {"rateLow90": low, "rateHigh90": high})
        result = pl.DataFrame(rows)

    result = result.with_columns(
        rankScore=pl.when(pl.col("anyCost")).then(pl.col("count") * pl.col("avgCost").fill_null(0).abs()).otherwise(pl.col("count").cast(pl.Float64))
    )
    result = result.sort("rankScore", descending=True)
    result = result.with_columns(patternId=pl.int_range(pl.len()).cast(pl.Utf8))
    return result


def main() -> None:
    thresholds = load_thresholds()
    flags = pl.read_parquet(PROCESSED_DIR / "flags.parquet")
    plays = pl.read_parquet(PROCESSED_DIR / "plays.parquet")
    games = pl.read_parquet(PROCESSED_DIR / "games.parquet")
    player_measurements = pl.read_parquet(PROCESSED_DIR / "player_measurements.parquet")

    situations = build_situation_table(plays, games, thresholds.patterns.distance_bands)

    from pipeline.detect.level2 import find_crossing_pairs
    from pipeline.features import _dropback_frame, _windowed_tracking

    tracking_norm = pl.read_parquet(PROCESSED_DIR / "tracking_norm.parquet")
    plays_resolved = _dropback_frame()
    window = _windowed_tracking(tracking_norm, plays_resolved)
    crossing_pairs = find_crossing_pairs(window, thresholds.level2.stunt_window_s)

    patterns = build_patterns(
        flags, situations, player_measurements, crossing_pairs,
        thresholds.patterns.min_opportunities, thresholds.patterns.interval_confidence,
    )
    patterns.write_parquet(PROCESSED_DIR / "patterns.parquet")
    print(f"Wrote patterns.parquet ({patterns.height} patterns with >= {thresholds.patterns.min_opportunities} opportunities)")


if __name__ == "__main__":
    main()
