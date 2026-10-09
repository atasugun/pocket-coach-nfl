import polars as pl
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.detect.split import (
    leave_one_game_out_history,
    shrink_toward_group,
    train_test_split_by_game,
)


@given(game_ids=st.lists(st.integers(min_value=1, max_value=100000), min_size=1, max_size=200, unique=True))
@settings(max_examples=100)
def test_property_10_train_test_disjoint(game_ids):
    """Property 10: train and test game sets are disjoint; every game is
    on exactly one side. Validates Requirement 7.6."""
    train, test = train_test_split_by_game(game_ids)
    assert train.isdisjoint(test)
    assert train | test == set(game_ids)


def test_split_is_deterministic_across_calls():
    ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    t1 = train_test_split_by_game(ids, seed=42)
    t2 = train_test_split_by_game(ids, seed=42)
    assert t1 == t2


def test_property_11_leave_one_game_out_excludes_own_game():
    """Property 11: every game contributing to a play's held-out feature
    is a training game — never the play's own game. Validates
    Requirement 7.7."""
    reps = pl.DataFrame(
        {
            "gameId": [1, 1, 2, 2, 3],
            "nflId": [10, 10, 10, 10, 10],
            "metric": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    hist = leave_one_game_out_history(reps, "metric")
    # For game 1 (2 reps: 1.0, 2.0), the leave-one-out mean should be the
    # average of games 2 and 3's rows only: (3+4+5)/3 = 4.0.
    row = hist.filter((pl.col("gameId") == 1) & (pl.col("nflId") == 10))
    assert abs(row["playerMean"][0] - 4.0) < 1e-9
    assert row["reps"][0] == 3

    row3 = hist.filter((pl.col("gameId") == 3) & (pl.col("nflId") == 10))
    assert abs(row3["playerMean"][0] - 2.5) < 1e-9  # avg of games 1&2: (1+2+3+4)/4


@given(
    player_mean=st.floats(min_value=-10, max_value=10, allow_nan=False),
    group_mean=st.floats(min_value=-10, max_value=10, allow_nan=False),
    reps=st.integers(min_value=0, max_value=100000),
    rep_threshold=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=150)
def test_property_12_shrinkage_is_convex_combination(player_mean, group_mean, reps, rep_threshold):
    """Property 12: the shrunk estimate lies between the raw estimate and
    the position average, approaches the group mean as reps -> 0, and the
    player's own mean as reps grows large. Validates Requirement 7.8."""
    shrunk = shrink_toward_group(player_mean, group_mean, reps, rep_threshold)
    lo, hi = min(player_mean, group_mean), max(player_mean, group_mean)
    assert lo - 1e-9 <= shrunk <= hi + 1e-9

    near_zero = shrink_toward_group(player_mean, group_mean, 0, rep_threshold)
    assert abs(near_zero - group_mean) < 1e-9

    near_inf = shrink_toward_group(player_mean, group_mean, 10_000_000, rep_threshold)
    assert abs(near_inf - player_mean) < 1e-3
