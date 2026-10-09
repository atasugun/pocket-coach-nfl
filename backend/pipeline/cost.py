"""nflverse EPA cost engine (Requirement 8): auto-download with local
caching, merge onto flags, team-perspective sign, equal split across
multiple flags on one play, graceful degradation when offline/unmatched.
"""
from __future__ import annotations

import polars as pl
import requests

from pipeline.config import REPO_ROOT

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
EPA_CACHE_PATH = PROCESSED_DIR / "epa_cache.parquet"
NFLVERSE_URL_TEMPLATE = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"


def download_epa(season: int = 2021, timeout: int = 60) -> pl.DataFrame | None:
    """Auto-download nflverse play-by-play EPA, caching locally
    (Requirement 8.4). Returns None (graceful degradation) if offline."""
    if EPA_CACHE_PATH.exists():
        return pl.read_parquet(EPA_CACHE_PATH)
    try:
        resp = requests.get(NFLVERSE_URL_TEMPLATE.format(season=season), timeout=timeout)
        resp.raise_for_status()
        tmp_path = PROCESSED_DIR / f"_pbp_{season}_download.parquet"
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(resp.content)
        pbp = pl.read_parquet(tmp_path)
        epa = pbp.select(
            pl.col("old_game_id").cast(pl.Int64).alias("gameId"),
            pl.col("play_id").cast(pl.Int64).alias("playId"),
            pl.col("epa"),
            pl.col("posteam"),
            pl.col("defteam"),
        ).drop_nulls(["gameId", "playId"])
        epa.write_parquet(EPA_CACHE_PATH)
        tmp_path.unlink(missing_ok=True)
        return epa
    except Exception as exc:  # noqa: BLE001 - any network/parse failure degrades gracefully
        print(f"EPA source unavailable ({exc}); flags will have epaCost=null.")
        return None


def attach_cost(flags: pl.DataFrame, epa: pl.DataFrame | None, plays: pl.DataFrame) -> pl.DataFrame:
    """Team-perspective cost, equal split across a play's flags, null when
    offline/unmatched (Requirement 8.2, 8.3, 8.5, 8.6, 8.8)."""
    output_cols = [
        "flagId", "gameId", "playId", "errorFrameId", "involvedNflIds",
        "team", "errorType", "confidenceLevel", "explanation", "epaCost", "detail",
    ]
    if epa is None or flags.height == 0:
        return flags.with_columns(epaCost=pl.lit(None, dtype=pl.Float64)).select(output_cols)

    defense_by_play = plays.select("gameId", "playId", pl.col("defensiveTeam").alias("defense"))
    merged = flags.join(epa, on=["gameId", "playId"], how="left").join(defense_by_play, on=["gameId", "playId"], how="left")

    # Team perspective: flip the EPA sign when the flag is charged to the
    # team that was NOT in possession (a defensive error) so a defensive
    # breakdown that helped the offense reads as a positive charge against
    # the defense.
    merged = merged.with_columns(
        teamEpa=pl.when(pl.col("team") == pl.col("posteam"))
        .then(pl.col("epa"))
        .when(pl.col("team") == pl.col("defense"))
        .then(-pl.col("epa"))
        .otherwise(None)
    )

    counts = merged.group_by(["gameId", "playId"]).agg(k=pl.col("flagId").len())
    merged = merged.join(counts, on=["gameId", "playId"], how="left")
    merged = merged.with_columns(
        epaCost=pl.when(pl.col("teamEpa").is_not_null()).then(pl.col("teamEpa") / pl.col("k")).otherwise(None)
    )

    return merged.select(output_cols)


def main() -> None:
    # Cost is shared across ALL flags on a play regardless of confidence
    # level (Requirement 8.3, Property 13), so every level's flags must be
    # combined before the per-play split is computed — splitting each
    # level's file separately would double-count the play's EPA.
    level_files = ["flags_level1.parquet", "flags_level2.parquet", "flags_level3.parquet"]
    frames = [pl.read_parquet(PROCESSED_DIR / f).drop("epaCost") for f in level_files if (PROCESSED_DIR / f).exists()]
    flags = pl.concat(frames, how="vertical")
    plays = pl.read_parquet(PROCESSED_DIR / "plays.parquet")

    epa = download_epa()
    flags = attach_cost(flags, epa, plays)
    flags.write_parquet(PROCESSED_DIR / "flags.parquet")

    for level, f in zip(["Confirmed", "Likely", "Possible"], level_files):
        if (PROCESSED_DIR / f).exists():
            flags.filter(pl.col("confidenceLevel") == level).write_parquet(PROCESSED_DIR / f)

    n_costed = flags.filter(pl.col("epaCost").is_not_null()).height
    print(f"Wrote flags.parquet ({flags.height} flags, {'offline' if epa is None else 'live/cached'} EPA); {n_costed} have a cost.")


if __name__ == "__main__":
    main()
