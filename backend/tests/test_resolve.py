import polars as pl

from pipeline.resolve import resolve_play_frames


def _tracking(events: dict[int, str]) -> pl.DataFrame:
    """Build a minimal play_tracking frame from {frameId: event}."""
    max_frame = max(events)
    rows = [
        {"frameId": f, "event": events.get(f, "None")}
        for f in range(1, max_frame + 1)
    ]
    return pl.DataFrame(rows)


def test_manual_snap_preferred_over_automatic():
    tracking = _tracking({3: "autoevent_ballsnap", 5: "ball_snap", 20: "pass_forward"})
    r = resolve_play_frames(tracking)
    assert r.resolved
    assert r.snap_frame_id == 5  # manual wins even though automatic fired earlier


def test_automatic_snap_used_when_no_manual():
    tracking = _tracking({4: "autoevent_ballsnap", 20: "pass_forward"})
    r = resolve_play_frames(tracking)
    assert r.resolved
    assert r.snap_frame_id == 4


def test_end_precedence_pass_forward_over_autoevent():
    tracking = _tracking({5: "ball_snap", 18: "autoevent_passforward", 20: "pass_forward"})
    r = resolve_play_frames(tracking)
    assert r.resolved
    assert r.end_of_dropback_frame_id == 20


def test_end_precedence_sack_used_when_no_pass_forward():
    tracking = _tracking({5: "ball_snap", 25: "qb_sack"})
    r = resolve_play_frames(tracking)
    assert r.resolved
    assert r.end_of_dropback_frame_id == 25


def test_end_precedence_strip_sack():
    tracking = _tracking({5: "ball_snap", 25: "qb_strip_sack"})
    r = resolve_play_frames(tracking)
    assert r.resolved
    assert r.end_of_dropback_frame_id == 25


def test_end_precedence_scramble_run():
    tracking = _tracking({5: "ball_snap", 30: "run"})
    r = resolve_play_frames(tracking)
    assert r.resolved
    assert r.end_of_dropback_frame_id == 30


def test_end_falls_back_to_last_recognized_terminal_event():
    tracking = _tracking({5: "ball_snap", 40: "tackle"})
    r = resolve_play_frames(tracking)
    assert r.resolved
    assert r.end_of_dropback_frame_id == 40


def test_unresolved_no_snap():
    tracking = _tracking({20: "pass_forward"})
    r = resolve_play_frames(tracking)
    assert not r.resolved
    assert r.reason == "no_snap_event"
    assert r.snap_frame_id is None


def test_unresolved_no_end():
    tracking = _tracking({5: "ball_snap"})
    r = resolve_play_frames(tracking)
    assert not r.resolved
    assert r.reason == "no_end_of_dropback_event"
    assert r.snap_frame_id == 5


def test_unresolved_end_before_snap():
    tracking = _tracking({20: "ball_snap", 5: "pass_forward"})
    r = resolve_play_frames(tracking)
    assert not r.resolved
    assert r.reason == "end_precedes_snap"
