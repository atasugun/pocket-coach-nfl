"""Thin query layer over the processed Parquet tables. Uses Polars'
predicate-pushdown scan so a single-play request never loads a whole game
into memory (Requirement 2.5, 1.6) — `scan_parquet(...).filter(...)` prunes
row groups before anything is materialized.
"""
from __future__ import annotations

from functools import lru_cache

import polars as pl

from pipeline.config import REPO_ROOT

PROCESSED_DIR = REPO_ROOT / "data" / "processed"


@lru_cache(maxsize=1)
def games() -> pl.DataFrame:
    return pl.read_parquet(PROCESSED_DIR / "games.parquet")


@lru_cache(maxsize=1)
def plays() -> pl.DataFrame:
    return pl.read_parquet(PROCESSED_DIR / "plays.parquet")


@lru_cache(maxsize=1)
def play_features() -> pl.DataFrame:
    return pl.read_parquet(PROCESSED_DIR / "play_features.parquet")


@lru_cache(maxsize=1)
def flags() -> pl.DataFrame:
    return pl.read_parquet(PROCESSED_DIR / "flags.parquet")


@lru_cache(maxsize=1)
def patterns() -> pl.DataFrame:
    return pl.read_parquet(PROCESSED_DIR / "patterns.parquet")


@lru_cache(maxsize=1)
def player_measurements() -> pl.DataFrame:
    return pl.read_parquet(PROCESSED_DIR / "player_measurements.parquet")


@lru_cache(maxsize=1)
def players() -> pl.DataFrame:
    return pl.read_parquet(PROCESSED_DIR / "players.parquet")


@lru_cache(maxsize=1)
def pocket_by_frame() -> pl.DataFrame:
    return pl.read_parquet(PROCESSED_DIR / "pocket_by_frame.parquet")


def scan_tracking_for_play(game_id: int, play_id: int) -> pl.DataFrame:
    """Predicate-pushdown slice of one play's frames only; never scans or
    materializes a whole game."""
    return (
        pl.scan_parquet(PROCESSED_DIR / "tracking_norm.parquet")
        .filter((pl.col("gameId") == game_id) & (pl.col("playId") == play_id))
        .collect()
    )


def games_between(my_team: str, opponent: str) -> list[int]:
    g = games()
    matched = g.filter(
        ((pl.col("homeTeamAbbr") == my_team) & (pl.col("visitorTeamAbbr") == opponent))
        | ((pl.col("homeTeamAbbr") == opponent) & (pl.col("visitorTeamAbbr") == my_team))
    )
    return matched["gameId"].to_list()


def team_abbrs() -> list[str]:
    g = games()
    return sorted(set(g["homeTeamAbbr"].to_list()) | set(g["visitorTeamAbbr"].to_list()))
