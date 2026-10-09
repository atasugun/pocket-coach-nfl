import polars as pl

from pipeline.cost import attach_cost
from pipeline.detect.flag import FLAG_SCHEMA


def _flag(game_id, play_id, flag_id, team, error_type="sack_allowed"):
    return {
        "flagId": flag_id, "gameId": game_id, "playId": play_id, "errorFrameId": 10,
        "involvedNflIds": [1], "team": team, "errorType": error_type,
        "confidenceLevel": "Confirmed", "explanation": "x", "epaCost": None, "detail": "{}",
    }


def _plays(rows):
    return pl.DataFrame(
        {
            "gameId": [r[0] for r in rows], "playId": [r[1] for r in rows],
            "defensiveTeam": [r[2] for r in rows],
        }
    )


def test_matched_play_gets_team_perspective_value():
    flags = pl.DataFrame([_flag(1, 1, "f1", "KC")], schema=FLAG_SCHEMA)
    epa = pl.DataFrame({"gameId": [1], "playId": [1], "epa": [1.5], "posteam": ["KC"], "defteam": ["BUF"]})
    plays = _plays([(1, 1, "BUF")])
    out = attach_cost(flags, epa, plays)
    assert abs(out["epaCost"][0] - 1.5) < 1e-9


def test_unmatched_play_gets_null_cost():
    flags = pl.DataFrame([_flag(1, 2, "f1", "KC")], schema=FLAG_SCHEMA)
    epa = pl.DataFrame({"gameId": [1], "playId": [1], "epa": [1.5], "posteam": ["KC"], "defteam": ["BUF"]})
    plays = _plays([(1, 2, "BUF")])
    out = attach_cost(flags, epa, plays)
    assert out["epaCost"][0] is None


def test_offline_source_degrades_to_null_without_failing():
    flags = pl.DataFrame([_flag(1, 1, "f1", "KC")], schema=FLAG_SCHEMA)
    plays = _plays([(1, 1, "BUF")])
    out = attach_cost(flags, None, plays)
    assert out["epaCost"][0] is None
    assert out.height == 1


def test_defensive_error_flips_epa_sign():
    flags = pl.DataFrame([_flag(1, 1, "f1", "BUF", error_type="lost_escape_lane")], schema=FLAG_SCHEMA)
    epa = pl.DataFrame({"gameId": [1], "playId": [1], "epa": [1.5], "posteam": ["KC"], "defteam": ["BUF"]})
    plays = _plays([(1, 1, "BUF")])
    out = attach_cost(flags, epa, plays)
    assert abs(out["epaCost"][0] - (-1.5)) < 1e-9


def test_property_13_shared_costs_sum_to_play_epa():
    flags = pl.DataFrame(
        [_flag(1, 1, "f1", "KC"), _flag(1, 1, "f2", "KC"), _flag(1, 1, "f3", "KC")], schema=FLAG_SCHEMA
    )
    epa = pl.DataFrame({"gameId": [1], "playId": [1], "epa": [3.0], "posteam": ["KC"], "defteam": ["BUF"]})
    plays = _plays([(1, 1, "BUF")])
    out = attach_cost(flags, epa, plays)
    assert all(abs(v - 1.0) < 1e-9 for v in out["epaCost"].to_list())
    assert abs(out["epaCost"].sum() - 3.0) < 1e-9
