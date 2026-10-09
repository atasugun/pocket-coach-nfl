import polars as pl

from pipeline.detect.level2 import (
    countable_blocker_count,
    detect_free_rusher,
    detect_lost_escape_lane,
    detect_wasted_double_team,
    find_crossing_pairs,
)


def test_countable_blocker_count_excludes_ch_sr_nb():
    pff = pl.DataFrame(
        {
            "gameId": [1, 1, 1, 1, 1],
            "playId": [1, 1, 1, 1, 1],
            "nflId": [10, 11, 12, 13, 14],
            "pff_role": ["Pass Block"] * 5,
            "pff_blockType": ["PP", "BH", "CH", "SR", "NB"],
        }
    )
    counts = countable_blocker_count(pff, ("CH", "SR", "NB"))
    assert counts["countableBlockerCount"][0] == 2  # only PP and BH count


def test_free_rusher_error_frame_and_attribution():
    player_measurements = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "nflId": [300],
            "timeToPressure": [0.8], "hadEngagement": [False],
            "closestApproachDist": [1.0],
        }
    )
    play_features = pl.DataFrame({"gameId": [1], "playId": [1], "rusherCount": [4]})
    blocker_counts = pl.DataFrame({"gameId": [1], "playId": [1], "countableBlockerCount": [5]})
    plays_resolved = pl.DataFrame(
        {"gameId": [1], "playId": [1], "snapFrameId": [10], "possessionTeam": ["KC"]}
    )
    window = pl.DataFrame(
        {
            "gameId": [1, 1], "playId": [1, 1], "frameId": [18, 18],
            "pff_role": ["Pass Block", "Pass Rush"], "nflId": [20, 300],
            "x": [30.0, 25.0], "y": [25.0, 25.0],
        }
    )
    from pipeline.config import load_thresholds

    flags = detect_free_rusher(
        plays_resolved, player_measurements, play_features, blocker_counts, window, load_thresholds()
    )
    assert len(flags) == 1
    f = flags[0]
    assert f["errorType"] == "free_rusher"
    assert f["errorFrameId"] == 18  # snap(10) + round(0.8*10) = 18
    assert 300 in f["involvedNflIds"]
    assert f["team"] == "KC"
    assert f["confidenceLevel"] == "Likely"


def test_wasted_double_team_requires_a_genuinely_free_rusher():
    """A double-teamed rusher alone should not fire; it needs another
    rusher on the same play with zero engagements."""
    engagements = pl.DataFrame(
        {
            "gameId": [1, 1], "playId": [1, 1],
            "blockerNflId": [10, 11], "rusherNflId": [300, 300],
            "startFrameId": [12, 14], "endFrameId": [20, 22], "minDistance": [1.0, 1.1],
        }
    )
    plays_resolved = pl.DataFrame(
        {"gameId": [1], "playId": [1], "snapFrameId": [10], "possessionTeam": ["KC"]}
    )

    # No free rusher at all -> no flag.
    pm_no_free = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "nflId": [301],
            "hadEngagement": [True], "closestApproachDist": [2.0],
        }
    )
    assert detect_wasted_double_team(engagements, pm_no_free, plays_resolved) == []

    # A free rusher (closestApproachDist present, hadEngagement False) -> flag.
    pm_with_free = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "nflId": [301],
            "hadEngagement": [False], "closestApproachDist": [6.0],
        }
    )
    flags = detect_wasted_double_team(engagements, pm_with_free, plays_resolved)
    assert len(flags) == 1
    f = flags[0]
    assert f["errorType"] == "wasted_double_team"
    assert f["errorFrameId"] == 14  # later of the two double-team start frames
    assert set(f["involvedNflIds"]) == {10, 11, 301}


def test_wasted_double_team_ignores_blocker_rows_masquerading_as_free():
    """Regression: blocker rows also carry hadEngagement=False in
    player_measurements (they're only ever joined against rusher ids), so
    the free-rusher check must require a rusher-only column
    (closestApproachDist) or every double team on the play would wrongly
    fire."""
    engagements = pl.DataFrame(
        {
            "gameId": [1, 1], "playId": [1, 1],
            "blockerNflId": [10, 11], "rusherNflId": [300, 300],
            "startFrameId": [12, 14], "endFrameId": [20, 22], "minDistance": [1.0, 1.1],
        }
    )
    plays_resolved = pl.DataFrame(
        {"gameId": [1], "playId": [1], "snapFrameId": [10], "possessionTeam": ["KC"]}
    )
    blocker_row = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "nflId": [99],
            "hadEngagement": [False], "closestApproachDist": [None],
        },
        schema={"gameId": pl.Int64, "playId": pl.Int64, "nflId": pl.Int64, "hadEngagement": pl.Boolean, "closestApproachDist": pl.Float64},
    )
    assert detect_wasted_double_team(engagements, blocker_row, plays_resolved) == []


def test_find_crossing_pairs_detects_lateral_order_flip():
    window = pl.DataFrame(
        {
            "gameId": [1] * 6, "playId": [1] * 6,
            "frameId": [10, 11, 12, 10, 11, 12],
            "pff_role": ["Pass Rush"] * 6,
            "nflId": [500, 500, 500, 600, 600, 600],
            "y": [20.0, 21.0, 22.0, 24.0, 22.0, 20.0],
            "snapFrameId": [10] * 6,
        }
    )
    pairs = find_crossing_pairs(window, stunt_window_s=2.0)
    assert pairs.height == 1
    row = pairs.row(0, named=True)
    assert {row["rusherA"], row["rusherB"]} == {500, 600}
    assert row["crossFrameId"] == 12  # frame at which the flipped order is observed


def test_lost_escape_lane_fires_only_on_scramble_with_both_edges_inside():
    plays_resolved = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "snapFrameId": [1],
            "passResult": ["R"], "defensiveTeam": ["BUF"],
        }
    )
    pff = pl.DataFrame(
        {"gameId": [1, 1], "playId": [1, 1], "nflId": [700, 701], "pff_positionLinedUp": ["LE", "RE"]}
    )
    # Tackle box: blockers at snap spread y 20-30 (center 25, halfWidth 5).
    window = pl.DataFrame(
        {
            "gameId": [1] * 5, "playId": [1] * 5,
            "frameId": [1, 1, 1, 1, 1],
            "pff_role": ["Pass Block", "Pass Block", "Pass", "Pass Rush", "Pass Rush"],
            "nflId": [10, 11, 1, 700, 701],
            "x": [30.0, 30.0, 28.0, 31.0, 31.0],
            "y": [20.0, 30.0, 40.0, 26.0, 24.0],  # QB well outside box; both edges inside him
            "snapFrameId": [1, 1, 1, 1, 1],
        }
    )
    flags = detect_lost_escape_lane(window, plays_resolved, pff)
    assert len(flags) == 1
    f = flags[0]
    assert f["errorType"] == "lost_escape_lane"
    assert f["team"] == "BUF"
    assert set(f["involvedNflIds"]) == {700, 701}


def test_lost_escape_lane_does_not_fire_without_scramble():
    plays_resolved = pl.DataFrame(
        {
            "gameId": [1], "playId": [1], "snapFrameId": [1],
            "passResult": ["C"], "defensiveTeam": ["BUF"],
        }
    )
    pff = pl.DataFrame(
        {"gameId": [1, 1], "playId": [1, 1], "nflId": [700, 701], "pff_positionLinedUp": ["LE", "RE"]}
    )
    window = pl.DataFrame(schema={"gameId": pl.Int64, "playId": pl.Int64, "frameId": pl.Int64})
    assert detect_lost_escape_lane(window, plays_resolved, pff) == []
