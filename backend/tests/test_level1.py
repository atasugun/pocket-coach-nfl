import polars as pl

from pipeline.detect.level1 import detect_allowed_pressure, detect_beaten, detect_penalties


def _bounds(game_id=1, play_id=1, last_frame=40):
    return pl.DataFrame({"gameId": [game_id], "playId": [play_id], "lastFrameId": [last_frame]})


def _player_team(game_id=1, play_id=1, rows=None):
    rows = rows or []
    return pl.DataFrame(
        {
            "gameId": [game_id] * len(rows),
            "playId": [play_id] * len(rows),
            "nflId": [r[0] for r in rows],
            "team": [r[1] for r in rows],
        },
        schema={"gameId": pl.Int64, "playId": pl.Int64, "nflId": pl.Int64, "team": pl.Utf8},
    )


def test_penalty_attributed_to_player_at_snap_frame():
    plays = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "snapFrameId": [5],
            "foulName1": ["Holding"], "foulNFLId1": [100],
            "foulName2": [None], "foulNFLId2": [None],
            "foulName3": [None], "foulNFLId3": [None],
        }
    )
    bounds = _bounds(last_frame=40)
    player_team = _player_team(rows=[(100, "KC")])

    flags = detect_penalties(plays, bounds, player_team)
    assert len(flags) == 1
    f = flags[0]
    assert f["errorType"] == "penalty"
    assert f["errorFrameId"] == 5
    assert f["involvedNflIds"] == [100]
    assert f["team"] == "KC"
    assert f["confidenceLevel"] == "Confirmed"


def test_no_penalty_flag_when_foul_nfl_id_is_na():
    plays = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "snapFrameId": [5],
            "foulName1": [None], "foulNFLId1": [None],
            "foulName2": [None], "foulNFLId2": [None],
            "foulName3": [None], "foulNFLId3": [None],
        }
    )
    flags = detect_penalties(plays, _bounds(), _player_team())
    assert flags == []


def test_sack_allowed_error_frame_is_rushers_closest_approach():
    pff = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "nflId": [200],
            "pff_sackAllowed": [1], "pff_hitAllowed": [None], "pff_hurryAllowed": [None],
            "pff_nflIdBlockedPlayer": [300],
        }
    )
    engagements = pl.DataFrame(
        schema={
            "gameId": pl.Int64, "playId": pl.Int64, "blockerNflId": pl.Int64,
            "rusherNflId": pl.Int64, "minDistance": pl.Float64,
        }
    )
    player_measurements = pl.DataFrame(
        {"gameId": [1], "playId": [1], "nflId": [300], "closestApproachFrameId": [22]}
    )
    plays_resolved = pl.DataFrame(
        {"gameId": [1], "playId": [1], "snapFrameId": [5], "possessionTeam": ["KC"]}
    )
    bounds = _bounds(last_frame=40)

    flags = detect_allowed_pressure(pff, engagements, player_measurements, plays_resolved, bounds)
    assert len(flags) == 1
    f = flags[0]
    assert f["errorType"] == "sack_allowed"
    assert f["errorFrameId"] == 22
    assert set(f["involvedNflIds"]) == {200, 300}
    assert f["team"] == "KC"


def test_no_fire_when_pff_label_is_na():
    pff = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "nflId": [200],
            "pff_sackAllowed": [None], "pff_hitAllowed": [None], "pff_hurryAllowed": [None],
            "pff_nflIdBlockedPlayer": [300],
        }
    )
    engagements = pl.DataFrame(
        schema={
            "gameId": pl.Int64, "playId": pl.Int64, "blockerNflId": pl.Int64,
            "rusherNflId": pl.Int64, "minDistance": pl.Float64,
        }
    )
    player_measurements = pl.DataFrame(
        schema={"gameId": pl.Int64, "playId": pl.Int64, "nflId": pl.Int64, "closestApproachFrameId": pl.Int64}
    )
    plays_resolved = pl.DataFrame(
        {"gameId": [1], "playId": [1], "snapFrameId": [5], "possessionTeam": ["KC"]}
    )
    flags = detect_allowed_pressure(pff, engagements, player_measurements, plays_resolved, _bounds())
    assert flags == []


def test_beaten_error_frame_is_pass_moment_from_engagement_end():
    pff = pl.DataFrame(
        {"gameId": [1], "playId": [1], "nflId": [200], "pff_beatenByDefender": [1], "pff_nflIdBlockedPlayer": [None]}
    )
    engagements = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "blockerNflId": [200], "rusherNflId": [300],
            "minDistance": [0.8], "endFrameId": [18],
        }
    )
    player_measurements = pl.DataFrame(
        {"gameId": [1], "playId": [1], "nflId": [300], "closestApproachFrameId": [25]}
    )
    plays_resolved = pl.DataFrame(
        {"gameId": [1], "playId": [1], "snapFrameId": [5], "possessionTeam": ["KC"]}
    )
    flags = detect_beaten(pff, engagements, player_measurements, plays_resolved, _bounds(last_frame=40))
    assert len(flags) == 1
    assert flags[0]["errorFrameId"] == 18  # engagement end, not closest approach


def test_beaten_falls_back_to_closest_approach_when_no_engagement():
    pff = pl.DataFrame(
        {"gameId": [1], "playId": [1], "nflId": [200], "pff_beatenByDefender": [1], "pff_nflIdBlockedPlayer": [300]}
    )
    engagements = pl.DataFrame(
        schema={
            "gameId": pl.Int64, "playId": pl.Int64, "blockerNflId": pl.Int64,
            "rusherNflId": pl.Int64, "minDistance": pl.Float64, "endFrameId": pl.Int64,
        }
    )
    player_measurements = pl.DataFrame(
        {"gameId": [1], "playId": [1], "nflId": [300], "closestApproachFrameId": [25]}
    )
    plays_resolved = pl.DataFrame(
        {"gameId": [1], "playId": [1], "snapFrameId": [5], "possessionTeam": ["KC"]}
    )
    flags = detect_beaten(pff, engagements, player_measurements, plays_resolved, _bounds(last_frame=40))
    assert len(flags) == 1
    assert flags[0]["errorFrameId"] == 25  # fallback to closest approach


def test_every_flag_resolvable_within_play_bounds():
    """Property 7 (partial, for Level 1): errorFrameId always lies within
    [snapFrameId, lastFrameId]."""
    pff = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "nflId": [200],
            "pff_sackAllowed": [1], "pff_hitAllowed": [None], "pff_hurryAllowed": [None],
            "pff_nflIdBlockedPlayer": [300],
        }
    )
    engagements = pl.DataFrame(
        schema={
            "gameId": pl.Int64, "playId": pl.Int64, "blockerNflId": pl.Int64,
            "rusherNflId": pl.Int64, "minDistance": pl.Float64,
        }
    )
    # closestApproachFrameId deliberately outside [snap, last] to exercise clamping
    player_measurements = pl.DataFrame(
        {"gameId": [1], "playId": [1], "nflId": [300], "closestApproachFrameId": [999]}
    )
    plays_resolved = pl.DataFrame(
        {"gameId": [1], "playId": [1], "snapFrameId": [5], "possessionTeam": ["KC"]}
    )
    bounds = _bounds(last_frame=40)
    flags = detect_allowed_pressure(pff, engagements, player_measurements, plays_resolved, bounds)
    assert flags[0]["errorFrameId"] <= 40
    assert flags[0]["errorFrameId"] >= 5
    for f in flags:
        assert f["gameId"] and f["playId"] and f["errorFrameId"] is not None
        assert f["involvedNflIds"]
        assert f["team"]
        assert f["errorType"]
        assert f["confidenceLevel"]
        assert f["explanation"]
