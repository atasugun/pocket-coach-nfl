import polars as pl

from pipeline.patterns import build_patterns
from pipeline.detect.flag import FLAG_SCHEMA


def _flag(game_id, play_id, flag_id, nfl_id, team, error_type, cost):
    return {
        "flagId": flag_id, "gameId": game_id, "playId": play_id, "errorFrameId": 10,
        "involvedNflIds": [nfl_id], "team": team, "errorType": error_type,
        "confidenceLevel": "Confirmed", "explanation": "x", "epaCost": cost, "detail": "{}",
    }


def _situations(play_ids, team="KC"):
    return pl.DataFrame(
        {
            "gameId": [1] * len(play_ids), "playId": play_ids,
            "down": [1] * len(play_ids), "distanceBand": ["medium"] * len(play_ids),
            "fieldZone": ["midfield"] * len(play_ids), "scoreState": ["tied"] * len(play_ids),
            "situationKey": ["1|medium|midfield|tied"] * len(play_ids),
            "possessionTeam": [team] * len(play_ids), "defensiveTeam": ["BUF"] * len(play_ids),
        }
    )


def _player_measurements(play_ids, nfl_id):
    """Blocker-only rows (closestApproachDist null) giving `nfl_id` one
    pass-block rep per play, so opportunities == len(play_ids)."""
    return pl.DataFrame(
        {
            "gameId": [1] * len(play_ids), "playId": play_ids, "nflId": [nfl_id] * len(play_ids),
            "closestApproachDist": [None] * len(play_ids),
        },
        schema={"gameId": pl.Int64, "playId": pl.Int64, "nflId": pl.Int64, "closestApproachDist": pl.Float64},
    )


def _empty_crossing_pairs():
    return pl.DataFrame(schema={"gameId": pl.Int64, "playId": pl.Int64})


def test_pattern_hidden_below_min_opportunities():
    flags = pl.DataFrame([_flag(1, 1, "f1", 100, "KC", "sack_allowed", 1.0)], schema=FLAG_SCHEMA)
    situations = _situations([1])
    pm = _player_measurements([1], 100)  # only 1 opportunity
    patterns = build_patterns(flags, situations, pm, _empty_crossing_pairs(), min_opportunities=10, interval_confidence=0.90)
    assert patterns.height == 0


def test_pattern_shown_above_min_opportunities_with_well_formed_rate():
    play_ids = list(range(1, 21))  # 20 opportunities
    flags = pl.DataFrame(
        [_flag(1, pid, f"f{pid}", 100, "KC", "sack_allowed", 1.0) for pid in play_ids[:5]], schema=FLAG_SCHEMA
    )
    situations = _situations(play_ids)
    pm = _player_measurements(play_ids, 100)
    patterns = build_patterns(flags, situations, pm, _empty_crossing_pairs(), min_opportunities=10, interval_confidence=0.90)
    assert patterns.height == 1
    row = patterns.row(0, named=True)
    assert row["count"] == 5
    assert row["opportunities"] == 20
    assert abs(row["rate"] - 0.25) < 1e-9
    assert 0 <= row["rateLow90"] <= row["rate"] <= row["rateHigh90"] <= 1


def test_property_15_patterns_ranked_by_count_times_avg_cost():
    """Property 15: the emitted ordering is non-increasing in
    count x avgCost. Validates Requirement 9.6."""
    play_ids = list(range(1, 31))
    flags = []
    # Pattern A: 2 flags, cost 5 each -> rankScore 10
    flags += [_flag(1, pid, f"a{pid}", 100, "KC", "sack_allowed", 5.0) for pid in play_ids[:2]]
    # Pattern B: 6 flags, cost 1 each -> rankScore 6
    flags += [_flag(1, pid, f"b{pid}", 200, "KC", "hit_allowed", 1.0) for pid in play_ids[2:8]]
    flags_df = pl.DataFrame(flags, schema=FLAG_SCHEMA)

    situations = _situations(play_ids)
    pm = pl.concat([_player_measurements(play_ids, 100), _player_measurements(play_ids, 200)])
    patterns = build_patterns(flags_df, situations, pm, _empty_crossing_pairs(), min_opportunities=10, interval_confidence=0.90)

    scores = patterns["rankScore"].to_list()
    assert scores == sorted(scores, reverse=True)
    assert patterns.row(0, named=True)["nflId"] == 100  # rankScore 10 > 6
