"""Composed measurements on top of tracking_norm + geometry.py primitives
(Requirement 4). Writes `engagements`, `play_features`, `player_measurements`.

Only resolved, dropback-pass plays are processed; unresolved plays never
reach detection (Requirement 2.2/2.3's invariant).
"""
from __future__ import annotations

import polars as pl

from pipeline.config import REPO_ROOT, load_thresholds
from pipeline.geometry import distance, pocket_area, segments_cross

PROCESSED_DIR = REPO_ROOT / "data" / "processed"

EDGE_POSITIONS = {"LE", "RE", "OLB", "ROLB", "LOLB", "LEO", "REO"}


def _dropback_frame() -> pl.DataFrame:
    plays = pl.read_parquet(PROCESSED_DIR / "plays.parquet")
    resolution = pl.read_parquet(PROCESSED_DIR / "play_resolution.parquet")
    merged = plays.join(resolution, on=["gameId", "playId"], how="inner")
    is_dropback = pl.col("dropBackType").is_not_null()
    return merged.filter(is_dropback & pl.col("resolved"))


def _windowed_tracking(tracking_norm: pl.DataFrame, plays_resolved: pl.DataFrame) -> pl.DataFrame:
    """Tracking rows for resolved dropback plays only, restricted to the
    snap..end-of-dropback(+buffer) window."""
    keys = plays_resolved.select(
        "gameId", "playId", "snapFrameId", "endOfDropbackFrameId"
    )
    joined = tracking_norm.join(keys, on=["gameId", "playId"], how="inner")
    buffer_frames = 5
    return joined.filter(
        (pl.col("frameId") >= pl.col("snapFrameId"))
        & (pl.col("frameId") <= pl.col("endOfDropbackFrameId") + buffer_frames)
    )


# ---------------------------------------------------------------------------
# Engagements (Requirement 4.3)
# ---------------------------------------------------------------------------


def compute_engagements(
    tracking_window: pl.DataFrame, pff: pl.DataFrame, distance_yd: float, min_frames: int
) -> pl.DataFrame:
    blockers = tracking_window.filter(pl.col("pff_role") == "Pass Block").select(
        "gameId", "playId", "frameId",
        pl.col("nflId").alias("blockerNflId"),
        pl.col("x").alias("bx"), pl.col("y").alias("by"),
    )
    rushers = tracking_window.filter(pl.col("pff_role") == "Pass Rush").select(
        "gameId", "playId", "frameId",
        pl.col("nflId").alias("rusherNflId"),
        pl.col("x").alias("rx"), pl.col("y").alias("ry"),
    )

    pairs = blockers.join(rushers, on=["gameId", "playId", "frameId"], how="inner")
    pairs = pairs.with_columns(
        dist=((pl.col("bx") - pl.col("rx")) ** 2 + (pl.col("by") - pl.col("ry")) ** 2).sqrt()
    )
    close = pairs.filter(pl.col("dist") <= distance_yd)
    if close.height == 0:
        return pl.DataFrame(
            schema={
                "gameId": pl.Int64, "playId": pl.Int64,
                "blockerNflId": pl.Int64, "rusherNflId": pl.Int64,
                "startFrameId": pl.Int64, "endFrameId": pl.Int64, "minDistance": pl.Float64,
            }
        )

    close = close.sort(["gameId", "playId", "blockerNflId", "rusherNflId", "frameId"])
    close = close.with_columns(
        prev_frame=pl.col("frameId").shift(1).over(["gameId", "playId", "blockerNflId", "rusherNflId"])
    )
    close = close.with_columns(
        new_run=(pl.col("prev_frame").is_null() | ((pl.col("frameId") - pl.col("prev_frame")) != 1)).cast(pl.Int32)
    )
    close = close.with_columns(
        runId=pl.col("new_run").cum_sum().over(["gameId", "playId", "blockerNflId", "rusherNflId"])
    )

    engagements = (
        close.group_by(["gameId", "playId", "blockerNflId", "rusherNflId", "runId"])
        .agg(
            startFrameId=pl.col("frameId").min(),
            endFrameId=pl.col("frameId").max(),
            minDistance=pl.col("dist").min(),
            nFrames=pl.col("frameId").len(),
        )
        .filter(pl.col("nFrames") >= min_frames)
        .drop("runId", "nFrames")
    )

    blocked_player = pff.select(
        "gameId", "playId",
        pl.col("nflId").alias("blockerNflId"),
        pl.col("pff_nflIdBlockedPlayer"),
    )
    engagements = engagements.join(blocked_player, on=["gameId", "playId", "blockerNflId"], how="left")
    engagements = engagements.with_columns(
        pffBlockedConsistent=pl.when(pl.col("pff_nflIdBlockedPlayer").is_not_null())
        .then(pl.col("pff_nflIdBlockedPlayer") == pl.col("rusherNflId"))
        .otherwise(None)
    ).drop("pff_nflIdBlockedPlayer")

    return engagements


def compute_set_points(
    tracking_window: pl.DataFrame,
    resolved: pl.DataFrame,
    search_seconds: float,
    fallback_seconds: float,
    frame_rate_hz: int,
) -> pl.DataFrame:
    """Blocker_Set_Point (Requirement 4.8, 4.9): the velocity-stop frame
    within `search_seconds` of the snap; falls back to the frame nearest
    `fallback_seconds` after the snap when no clear stop occurs."""
    # tracking_window already carries snapFrameId (joined in _windowed_tracking).
    blockers = tracking_window.filter(pl.col("pff_role") == "Pass Block")
    search_frames = int(round(search_seconds * frame_rate_hz))
    fallback_frame_offset = int(round(fallback_seconds * frame_rate_hz))

    blockers = blockers.filter(
        (pl.col("frameId") - pl.col("snapFrameId") >= 0)
        & (pl.col("frameId") - pl.col("snapFrameId") <= search_frames)
    ).sort(["gameId", "playId", "nflId", "frameId"])

    # Forward speed component along the field: positive s_x means the
    # blocker is still back-pedalling toward his own end zone; "velocity
    # stop" is the first frame s_x crosses from negative-or-zero toward the
    # backfield to non-negative (i.e. he plants and stops retreating).
    blockers = blockers.with_columns(
        vx=(pl.col("x") - pl.col("x").shift(1).over(["gameId", "playId", "nflId"]))
    )
    stops = (
        blockers.filter(pl.col("vx").is_not_null() & (pl.col("vx") <= 0.01))
        .group_by(["gameId", "playId", "nflId"])
        .agg(setPointFrameId=pl.col("frameId").min())
        .with_columns(setPointFallbackUsed=pl.lit(False))
    )

    fallback = (
        blockers.with_columns(frame_offset=(pl.col("frameId") - pl.col("snapFrameId") - fallback_frame_offset).abs())
        .sort("frame_offset")
        .group_by(["gameId", "playId", "nflId"])
        .agg(setPointFrameId=pl.col("frameId").first())
        .with_columns(setPointFallbackUsed=pl.lit(True))
    )

    all_blockers = blockers.select("gameId", "playId", "nflId").unique()
    result = all_blockers.join(stops, on=["gameId", "playId", "nflId"], how="left")
    result = result.join(
        fallback, on=["gameId", "playId", "nflId"], how="left", suffix="_fb"
    )
    result = result.with_columns(
        setPointFrameId=pl.coalesce(["setPointFrameId", "setPointFrameId_fb"]),
        setPointFallbackUsed=pl.coalesce(["setPointFallbackUsed", "setPointFallbackUsed_fb"]),
    ).select("gameId", "playId", "nflId", "setPointFrameId", "setPointFallbackUsed")

    return result.rename({"nflId": "blockerNflId"})


# ---------------------------------------------------------------------------
# Pocket area / shrink (Requirement 4.1)
# ---------------------------------------------------------------------------


def compute_pocket_by_frame(tracking_window: pl.DataFrame) -> pl.DataFrame:
    pocket_members = tracking_window.filter(pl.col("pff_role").is_in(["Pass Block", "Pass"]))
    grouped = (
        pocket_members.group_by(["gameId", "playId", "frameId"])
        .agg(points=pl.concat_list([pl.col("x"), pl.col("y")]).implode())
    )

    def _area(points_col: list) -> float:
        pts = [(p[0], p[1]) for p in points_col]
        return pocket_area(pts) if len(pts) >= 3 else 0.0

    grouped = grouped.with_columns(
        pocketArea=pl.col("points").map_elements(_area, return_dtype=pl.Float64)
    ).drop("points")
    return grouped


def compute_pocket_shrink_rate(pocket_by_frame: pl.DataFrame, resolved: pl.DataFrame) -> pl.DataFrame:
    joined = pocket_by_frame.join(
        resolved.select("gameId", "playId", "snapFrameId"), on=["gameId", "playId"]
    ).with_columns(snapOffset=pl.col("frameId") - pl.col("snapFrameId"))

    def _slope(df: pl.DataFrame) -> float:
        xs = df["snapOffset"].to_list()
        ys = df["pocketArea"].to_list()
        n = len(xs)
        if n < 2:
            return 0.0
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den = sum((x - mean_x) ** 2 for x in xs)
        return num / den if den > 1e-9 else 0.0

    rows = []
    for (game_id, play_id), g in joined.group_by(["gameId", "playId"], maintain_order=True):
        rows.append({"gameId": game_id, "playId": play_id, "pocketShrinkRate": _slope(g)})
    return pl.DataFrame(rows, schema={"gameId": pl.Int64, "playId": pl.Int64, "pocketShrinkRate": pl.Float64})


# ---------------------------------------------------------------------------
# Per-rusher measurements (Requirement 4.2, 4.5, 4.6)
# ---------------------------------------------------------------------------


def compute_rusher_measurements(
    tracking_window: pl.DataFrame,
    resolved: pl.DataFrame,
    pff: pl.DataFrame,
    getoff_speed_yps: float,
    free_rusher_qb_yd: float,
) -> pl.DataFrame:
    rushers = tracking_window.filter(pl.col("pff_role") == "Pass Rush")
    qb = tracking_window.filter(pl.col("pff_role") == "Pass").select(
        "gameId", "playId", "frameId", pl.col("x").alias("qbx"), pl.col("y").alias("qby")
    )
    rushers = rushers.join(qb, on=["gameId", "playId", "frameId"], how="inner")
    rushers = rushers.with_columns(
        distToQb=((pl.col("x") - pl.col("qbx")) ** 2 + (pl.col("y") - pl.col("qby")) ** 2).sqrt()
    )
    # tracking_window already carries snapFrameId (joined in _windowed_tracking).

    getoff = (
        rushers.filter(pl.col("s") >= getoff_speed_yps)
        .group_by(["gameId", "playId", "nflId"])
        .agg(getOffFrameId=pl.col("frameId").min())
    )
    getoff = getoff.join(resolved.select("gameId", "playId", "snapFrameId"), on=["gameId", "playId"])
    getoff = getoff.with_columns(
        getOffTime=(pl.col("getOffFrameId") - pl.col("snapFrameId")) / 10.0
    ).select("gameId", "playId", "nflId", "getOffTime")

    closest = (
        rushers.sort("distToQb")
        .group_by(["gameId", "playId", "nflId"])
        .agg(
            closestApproachDist=pl.col("distToQb").first(),
            closestApproachFrameId=pl.col("frameId").filter(pl.col("distToQb") == pl.col("distToQb").min()).first(),
        )
    )

    time_to_pressure_rows = (
        rushers.filter(pl.col("distToQb") <= free_rusher_qb_yd)
        .group_by(["gameId", "playId", "nflId"])
        .agg(firstWithinFrameId=pl.col("frameId").min())
        .join(resolved.select("gameId", "playId", "snapFrameId"), on=["gameId", "playId"])
        .with_columns(timeToPressure=(pl.col("firstWithinFrameId") - pl.col("snapFrameId")) / 10.0)
        .select("gameId", "playId", "nflId", "timeToPressure")
    )

    reached_2_5s = (
        rushers.with_columns(elapsed=(pl.col("frameId") - pl.col("snapFrameId")) / 10.0)
        .filter((pl.col("distToQb") <= free_rusher_qb_yd) & (pl.col("elapsed") <= 2.5))
        .select("gameId", "playId", "nflId")
        .unique()
        .with_columns(reachedQbWithin2_5s=pl.lit(True))
    )

    speed_at_contact = (
        rushers.join(
            pff.select("gameId", "playId", pl.col("nflId"), "pff_blockType").rename({"nflId": "rusherNflId"}),
            left_on=["gameId", "playId", "nflId"], right_on=["gameId", "playId", "rusherNflId"], how="left",
        )
    )

    # inside/outside lateral direction, derived from pre-snap alignment
    # (edge positions rush "outside"; interior line positions rush "inside").
    alignment = pff.select("gameId", "playId", "nflId", "pff_positionLinedUp").with_columns(
        rushLateralDir=pl.when(pl.col("pff_positionLinedUp").is_in(list(EDGE_POSITIONS)))
        .then(pl.lit("outside"))
        .otherwise(pl.lit("inside"))
    ).select("gameId", "playId", "nflId", "rushLateralDir")

    base = rushers.select("gameId", "playId", "nflId").unique()
    out = (
        base.join(getoff, on=["gameId", "playId", "nflId"], how="left")
        .join(closest, on=["gameId", "playId", "nflId"], how="left")
        .join(time_to_pressure_rows, on=["gameId", "playId", "nflId"], how="left")
        .join(reached_2_5s, on=["gameId", "playId", "nflId"], how="left")
        .join(alignment, on=["gameId", "playId", "nflId"], how="left")
    )
    out = out.with_columns(reachedQbWithin2_5s=pl.col("reachedQbWithin2_5s").fill_null(False))
    return out


def compute_crossed_with_rusher(tracking_window: pl.DataFrame, resolved: pl.DataFrame) -> pl.DataFrame:
    """Whether a rusher's straight-line path (snap position -> end-of-window
    position) crossed another rusher's path on the same play."""
    rushers = tracking_window.filter(pl.col("pff_role") == "Pass Rush")
    endpoints = (
        rushers.sort("frameId")
        .group_by(["gameId", "playId", "nflId"])
        .agg(x0=pl.col("x").first(), y0=pl.col("y").first(), x1=pl.col("x").last(), y1=pl.col("y").last())
    )

    rows = []
    for (game_id, play_id), g in endpoints.group_by(["gameId", "playId"], maintain_order=True):
        ids = g["nflId"].to_list()
        crossed = {i: False for i in ids}
        segs = {
            row["nflId"]: ((row["x0"], row["y0"]), (row["x1"], row["y1"]))
            for row in g.iter_rows(named=True)
        }
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a1, a2 = segs[ids[i]]
                b1, b2 = segs[ids[j]]
                if segments_cross(a1, a2, b1, b2):
                    crossed[ids[i]] = True
                    crossed[ids[j]] = True
        for nfl_id, flag in crossed.items():
            rows.append({"gameId": game_id, "playId": play_id, "nflId": nfl_id, "crossedWithRusher": flag})

    if not rows:
        return pl.DataFrame(
            schema={"gameId": pl.Int64, "playId": pl.Int64, "nflId": pl.Int64, "crossedWithRusher": pl.Boolean}
        )
    return pl.DataFrame(rows)


# ---------------------------------------------------------------------------
# Depth conceded (Requirement 4.4)
# ---------------------------------------------------------------------------


def compute_depth_conceded(
    tracking_window: pl.DataFrame, resolved: pl.DataFrame, set_points: pl.DataFrame
) -> pl.DataFrame:
    blockers = tracking_window.filter(pl.col("pff_role") == "Pass Block").select(
        "gameId", "playId", pl.col("nflId").alias("blockerNflId"), "frameId", "x"
    )
    blockers = blockers.join(
        resolved.select("gameId", "playId", "snapFrameId"), on=["gameId", "playId"]
    )
    set_pt_x = blockers.join(
        set_points.select("gameId", "playId", "blockerNflId", "setPointFrameId"),
        on=["gameId", "playId", "blockerNflId"],
    ).filter(pl.col("frameId") == pl.col("setPointFrameId")).select(
        "gameId", "playId", "blockerNflId", pl.col("x").alias("setPointX")
    )

    blockers = blockers.with_columns(elapsed=(pl.col("frameId") - pl.col("snapFrameId")) / 10.0)
    blockers = blockers.join(set_pt_x, on=["gameId", "playId", "blockerNflId"], how="left")
    blockers = blockers.with_columns(depth=(pl.col("setPointX") - pl.col("x")))

    out_rows = []
    for t in (1.0, 1.5, 2.0, 2.5):
        snap = (
            blockers.with_columns(delta=(pl.col("elapsed") - t).abs())
            .sort("delta")
            .group_by(["gameId", "playId", "blockerNflId"])
            .agg(**{f"depthConceded_{str(t).replace('.', '_')}": pl.col("depth").first()})
        )
        out_rows.append(snap)

    base = blockers.select("gameId", "playId", "blockerNflId").unique()
    for snap_df in out_rows:
        base = base.join(snap_df, on=["gameId", "playId", "blockerNflId"], how="left")
    return base.rename({"blockerNflId": "nflId"})


# ---------------------------------------------------------------------------
# Play-level features
# ---------------------------------------------------------------------------


def compute_play_features(
    plays_resolved: pl.DataFrame,
    tracking_window: pl.DataFrame,
    pocket_by_frame: pl.DataFrame,
    shrink: pl.DataFrame,
    los: pl.DataFrame,
    pff: pl.DataFrame,
) -> pl.DataFrame:
    throw_events = tracking_window.filter(pl.col("event").is_in(["pass_forward", "autoevent_passforward"]))
    time_to_throw = (
        throw_events.group_by(["gameId", "playId"])
        .agg(throwFrameId=pl.col("frameId").min())
        .join(plays_resolved.select("gameId", "playId", "snapFrameId"), on=["gameId", "playId"])
        .with_columns(timeToThrow=(pl.col("throwFrameId") - pl.col("snapFrameId")) / 10.0)
        .select("gameId", "playId", "timeToThrow")
    )

    counts = (
        tracking_window.filter(pl.col("pff_role").is_in(["Pass Block", "Pass Rush"]))
        .group_by(["gameId", "playId", "pff_role"])
        .agg(nflIds=pl.col("nflId").unique())
        .with_columns(n=pl.col("nflIds").list.len())
        .pivot(values="n", index=["gameId", "playId"], on="pff_role")
        .rename({"Pass Block": "blockerCount", "Pass Rush": "rusherCount"})
    )

    had_pressure = (
        pff.with_columns(
            pressured=(pl.col("pff_hit") == 1) | (pl.col("pff_hurry") == 1) | (pl.col("pff_sack") == 1)
        )
        .group_by(["gameId", "playId"])
        .agg(hadPressure=pl.col("pressured").any())
    )

    pocket_arrays = (
        pocket_by_frame.sort("frameId")
        .group_by(["gameId", "playId"])
        .agg(pocketAreaBySnapOffset=pl.col("pocketArea"))
    )

    features = plays_resolved.select(
        "gameId", "playId", "snapFrameId", "endOfDropbackFrameId",
        "dropBackType", "passResult", "resolved", "unresolvedReason", "yardsToGo",
        pl.col("possessionTeam").alias("offense"), pl.col("defensiveTeam").alias("defense"),
    )
    features = features.join(los, on=["gameId", "playId"], how="left")
    features = features.with_columns(firstDownX=pl.col("lineOfScrimmage") + pl.col("yardsToGo"))
    features = features.join(time_to_throw, on=["gameId", "playId"], how="left")
    features = features.join(counts, on=["gameId", "playId"], how="left")
    features = features.join(pocket_arrays, on=["gameId", "playId"], how="left")
    features = features.join(shrink, on=["gameId", "playId"], how="left")
    features = features.join(had_pressure, on=["gameId", "playId"], how="left")
    features = features.with_columns(hadPressure=pl.col("hadPressure").fill_null(False))
    return features


def main() -> None:
    thresholds = load_thresholds()
    tracking_norm = pl.read_parquet(PROCESSED_DIR / "tracking_norm.parquet")
    pff = pl.read_parquet(PROCESSED_DIR / "pff_scouting.parquet")
    los = pl.read_parquet(PROCESSED_DIR / "line_of_scrimmage.parquet")

    plays_resolved = _dropback_frame()
    window = _windowed_tracking(tracking_norm, plays_resolved)

    engagements = compute_engagements(
        window, pff, thresholds.engagement.distance_yd, thresholds.engagement.min_consecutive_frames
    )
    set_points = compute_set_points(
        window,
        plays_resolved,
        thresholds.rusher.set_point_search_seconds,
        thresholds.rusher.set_point_fallback_seconds,
        thresholds.field.frame_rate_hz,
    )
    engagements = engagements.join(
        set_points, on=["gameId", "playId", "blockerNflId"], how="left"
    )
    engagements.write_parquet(PROCESSED_DIR / "engagements.parquet")

    pocket_by_frame = compute_pocket_by_frame(window)
    pocket_by_frame.write_parquet(PROCESSED_DIR / "pocket_by_frame.parquet")
    shrink = compute_pocket_shrink_rate(pocket_by_frame, plays_resolved)

    play_features = compute_play_features(plays_resolved, window, pocket_by_frame, shrink, los, pff)
    play_features.write_parquet(PROCESSED_DIR / "play_features.parquet")

    rusher_meas = compute_rusher_measurements(
        window, plays_resolved, pff, thresholds.rusher.getoff_speed_yps, thresholds.level2.free_rusher_qb_yd
    )
    crossed = compute_crossed_with_rusher(window, plays_resolved)
    rusher_meas = rusher_meas.join(crossed, on=["gameId", "playId", "nflId"], how="left")

    depth = compute_depth_conceded(window, plays_resolved, set_points)

    player_measurements = rusher_meas.join(
        depth, on=["gameId", "playId", "nflId"], how="full", coalesce=True
    )
    # rusherPassedBlocker: did the rusher's closest-approach beat the
    # free-rusher distance while an engagement with a blocker also existed?
    engaged_rushers = engagements.select("gameId", "playId", "rusherNflId").unique().with_columns(
        hadEngagement=pl.lit(True)
    ).rename({"rusherNflId": "nflId"})
    player_measurements = player_measurements.join(
        engaged_rushers, on=["gameId", "playId", "nflId"], how="left"
    ).with_columns(
        hadEngagement=pl.col("hadEngagement").fill_null(False),
        rusherPassedBlocker=pl.col("closestApproachDist").is_not_null()
        & (pl.col("closestApproachDist") <= thresholds.level2.free_rusher_qb_yd)
        & pl.col("hadEngagement"),
    )

    player_measurements.write_parquet(PROCESSED_DIR / "player_measurements.parquet")

    print(
        f"Wrote engagements.parquet ({engagements.height}), "
        f"play_features.parquet ({play_features.height}), "
        f"player_measurements.parquet ({player_measurements.height})"
    )


if __name__ == "__main__":
    main()
