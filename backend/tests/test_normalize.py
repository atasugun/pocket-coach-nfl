import polars as pl
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.normalize import add_time_since_snap, normalize_direction

FIELD_LENGTH = 120.0
FIELD_WIDTH = 53.3


def _row(x, y, o, d, direction):
    return {
        "gameId": 1, "playId": 1, "nflId": 1, "frameId": 1,
        "x": x, "y": y, "o": o, "dir": d, "playDirection": direction,
    }


@given(
    x=st.floats(min_value=0, max_value=FIELD_LENGTH, allow_nan=False),
    y=st.floats(min_value=0, max_value=FIELD_WIDTH, allow_nan=False),
    o=st.floats(min_value=0, max_value=359.999, allow_nan=False),
    d=st.floats(min_value=0, max_value=359.999, allow_nan=False),
)
@settings(max_examples=150)
def test_property_1_normalization_involutive_on_left_and_identity_on_right(x, y, o, d):
    """Property 1: applying the left-play normalization twice returns the
    original values, and a right-play row is left unchanged. Validates
    Requirement 3.1."""
    left_once = normalize_direction(
        pl.DataFrame([_row(x, y, o, d, "left")]), FIELD_LENGTH, FIELD_WIDTH
    )
    # Applying again to the same (still-left) row should return the original.
    left_twice = normalize_direction(left_once, FIELD_LENGTH, FIELD_WIDTH)
    row = left_twice.row(0, named=True)
    assert abs(row["x"] - x) < 1e-6
    assert abs(row["y"] - y) < 1e-6
    assert _angle_close(row["o"], o)
    assert _angle_close(row["dir"], d)

    right = normalize_direction(
        pl.DataFrame([_row(x, y, o, d, "right")]), FIELD_LENGTH, FIELD_WIDTH
    )
    right_row = right.row(0, named=True)
    assert abs(right_row["x"] - x) < 1e-6
    assert abs(right_row["y"] - y) < 1e-6
    assert _angle_close(right_row["o"], o)
    assert _angle_close(right_row["dir"], d)


def _angle_close(a, b, tol=1e-6):
    diff = abs((a - b) % 360)
    return diff < tol or abs(diff - 360) < tol


@given(n_frames=st.integers(min_value=1, max_value=50), snap_offset=st.integers(min_value=0, max_value=20))
@settings(max_examples=100)
def test_property_2_time_since_snap_monotonic_and_zero_at_snap(n_frames, snap_offset):
    """Property 2: timeSinceSnap increases by exactly 0.1s per frame and
    equals 0.0 at the snap frame. Validates Requirement 3.3."""
    snap_frame = snap_offset + 1
    frames = list(range(1, snap_offset + n_frames + 1))
    tracking = pl.DataFrame(
        {
            "gameId": [1] * len(frames),
            "playId": [1] * len(frames),
            "frameId": frames,
        }
    )
    resolved = pl.DataFrame({"gameId": [1], "playId": [1], "snapFrameId": [snap_frame]})

    out = add_time_since_snap(tracking, resolved, frame_rate_hz=10).sort("frameId")
    values = out["timeSinceSnap"].to_list()

    snap_idx = frames.index(snap_frame)
    assert abs(values[snap_idx] - 0.0) < 1e-9

    for i in range(1, len(values)):
        assert abs((values[i] - values[i - 1]) - 0.1) < 1e-9
