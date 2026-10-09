"""API tests run against the real processed Parquet tables (produced by
`make data`), so they double as an integration smoke test of the whole
pipeline-to-API path."""
import pytest
from fastapi.testclient import TestClient

from pipeline.config import REPO_ROOT

pytestmark = pytest.mark.skipif(
    not (REPO_ROOT / "data" / "processed" / "flags.parquet").exists(),
    reason="requires `make data` to have been run first",
)


@pytest.fixture(scope="module")
def client():
    from api.main import app

    return TestClient(app)


def test_plays_endpoint_returns_scoped_list(client):
    resp = client.get("/plays", params={"myTeam": "TB", "opponent": "DAL"})
    assert resp.status_code == 200
    plays = resp.json()
    assert len(plays) > 0
    assert all(p["offense"] in ("TB", "DAL") for p in plays)


def test_play_detail_returns_single_plays_frames_only(client):
    plays = client.get("/plays", params={"myTeam": "TB", "opponent": "DAL"}).json()
    game_id, play_id = plays[0]["gameId"], plays[0]["playId"]
    resp = client.get(f"/plays/{game_id}/{play_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "header" in body and "meta" in body and "frames" in body
    assert all(f["frameId"] for f in body["frames"])
    # Every object in every frame belongs to this one play (sanity: frames
    # list is non-trivial and consistently shaped, not a whole game dump).
    assert len(body["frames"]) < 200


def test_flags_scoping_by_mode(client):
    self_flags = client.get("/flags", params={"myTeam": "TB", "opponent": "DAL", "mode": "self"}).json()
    opp_flags = client.get("/flags", params={"myTeam": "TB", "opponent": "DAL", "mode": "opponent"}).json()
    assert all(f["team"] == "TB" for f in self_flags)
    assert all(f["team"] == "DAL" for f in opp_flags)


def test_limitations_note_present(client):
    resp = client.get("/limitations")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["bullets"]) == 4
