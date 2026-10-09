"""By-game train/test split, leakage-free player history, and low-rep
shrinkage (Requirement 7.6, 7.7, 7.8). Used by Level 2 calibration and the
Level 3 models. Splitting is strictly by gameId — never by random
frame/play — so a whole game's plays stay entirely on one side (Property 10).
"""
from __future__ import annotations

import hashlib

import polars as pl


def train_test_split_by_game(game_ids: list[int], test_frac: float = 0.2, seed: int = 0) -> tuple[set[int], set[int]]:
    """Deterministic by-game split via a stable hash, so the same gameId
    always lands on the same side across runs without needing to persist
    the split. Returns (train_game_ids, test_game_ids)."""
    unique_games = sorted(set(game_ids))
    test: set[int] = set()
    train: set[int] = set()
    for g in unique_games:
        digest = hashlib.sha1(f"{seed}:{g}".encode()).hexdigest()
        frac = int(digest[:8], 16) / 0xFFFFFFFF
        (test if frac < test_frac else train).add(g)
    return train, test


def leakage_free_player_history(
    player_reps: pl.DataFrame,
    train_game_ids: set[int],
    metric_col: str,
    group_cols: list[str] | None = None,
) -> pl.DataFrame:
    """Per-player average of `metric_col` computed from training games only
    (Requirement 7.7). `player_reps` must have gameId, nflId, and
    `metric_col`. When `group_cols` is given (e.g. position), averages are
    also computed per group for shrinkage targets."""
    group_cols = group_cols or []
    train_rows = player_reps.filter(pl.col("gameId").is_in(list(train_game_ids)))

    player_hist = (
        train_rows.group_by("nflId")
        .agg(
            playerMean=pl.col(metric_col).mean(),
            reps=pl.col(metric_col).count(),
        )
    )
    if group_cols:
        group_hist = (
            train_rows.group_by(group_cols)
            .agg(groupMean=pl.col(metric_col).mean())
        )
        key_cols = train_rows.select(["nflId", *group_cols]).unique()
        player_hist = player_hist.join(key_cols, on="nflId", how="left").join(
            group_hist, on=group_cols, how="left"
        )
    else:
        player_hist = player_hist.with_columns(groupMean=pl.col("playerMean").mean())

    return player_hist


def leave_one_game_out_history(
    player_reps: pl.DataFrame, metric_col: str, group_cols: list[str] | None = None
) -> pl.DataFrame:
    """For every (gameId, nflId), the player's average `metric_col` over
    every OTHER game only — so a play never uses history derived from its
    own game (Requirement 7.7, Property 11)."""
    group_cols = group_cols or []
    totals = player_reps.group_by("nflId").agg(
        sumAll=pl.col(metric_col).sum(), countAll=pl.col(metric_col).count()
    )
    per_game = player_reps.group_by(["gameId", "nflId"]).agg(
        sumGame=pl.col(metric_col).sum(), countGame=pl.col(metric_col).count()
    )
    out = per_game.join(totals, on="nflId", how="left")
    out = out.with_columns(
        reps=(pl.col("countAll") - pl.col("countGame")),
        playerMean=pl.when((pl.col("countAll") - pl.col("countGame")) > 0)
        .then((pl.col("sumAll") - pl.col("sumGame")) / (pl.col("countAll") - pl.col("countGame")))
        .otherwise(None),
    ).select("gameId", "nflId", "playerMean", "reps")
    return out


def shrink_toward_group(player_mean: float, group_mean: float, reps: int, rep_threshold: int) -> float:
    """Empirical-Bayes-style shrinkage (Requirement 7.8, Property 12): a
    convex combination of the player's own mean and the group average,
    weighted by how many reps the player has relative to `rep_threshold`.
    Approaches the group mean as reps -> 0 and the player's own mean as
    reps grows large."""
    weight = reps / (reps + rep_threshold)
    return weight * player_mean + (1 - weight) * group_mean
