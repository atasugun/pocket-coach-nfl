"""One-time conversion of the raw tracking CSVs to partitioned Parquet
(Requirement 2.5, 1.2). Downstream stages read this Parquet via Polars/DuckDB
and never re-read the raw CSVs per request.
"""
from __future__ import annotations

import polars as pl

from pipeline.config import REPO_ROOT

RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    tracking = pl.read_csv(RAW_DIR / "tracking" / "*.csv", null_values=["NA"])
    # Single Parquet file, sorted by gameId so DuckDB/Polars can still prune
    # by gameId via predicate pushdown on a sorted column's row-group stats.
    tracking = tracking.sort(["gameId", "playId", "nflId", "frameId"])
    tracking.write_parquet(PROCESSED_DIR / "tracking.parquet", statistics=True)

    games = pl.read_csv(RAW_DIR / "games.csv")
    games.write_parquet(PROCESSED_DIR / "games.parquet")

    plays = pl.read_csv(RAW_DIR / "plays.csv", null_values=["NA"])
    plays.write_parquet(PROCESSED_DIR / "plays.parquet")

    players = pl.read_csv(RAW_DIR / "players.csv", null_values=["NA"])
    players.write_parquet(PROCESSED_DIR / "players.parquet")

    pff = pl.read_csv(RAW_DIR / "pffScoutingData.csv", null_values=["NA"])
    pff.write_parquet(PROCESSED_DIR / "pff_scouting.parquet")

    print(f"Wrote tracking.parquet ({tracking.height} rows), games, plays, players, pff_scouting to {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
