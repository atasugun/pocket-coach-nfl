"""FastAPI service: plays, frames, flags, patterns, players, limitations.
Every endpoint scopes to `myTeam` + `opponent` + `mode` (+ optional `games`)
per Requirement 10.1-10.4; `/plays/{gameId}/{playId}` returns one play's
frames only, never a whole game (Requirement 2.5).
"""
from __future__ import annotations

import json
from typing import Literal

import polars as pl
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api import db

app = FastAPI(title="Pass Protection Error Finder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LIMITATIONS = {
    "title": "What this tool can't tell you",
    "bullets": [
        "The play call is unknown, so an error may be a design choice rather than a player mistake.",
        "Only pass plays are covered — there is no run-blocking analysis.",
        "Tracking data ends around the throw, sack, or scramble — what happens after is not captured.",
        "Eight weeks of games produces small samples; treat low-sample-size patterns with caution.",
    ],
}


def _scoped_game_ids(my_team: str | None, opponent: str | None, games_param: str | None) -> list[int] | None:
    if games_param:
        return [int(g) for g in games_param.split(",") if g]
    if my_team and opponent:
        return db.games_between(my_team, opponent)
    return None  # unscoped: no game filter


def _charged_team(my_team: str | None, opponent: str | None, mode: str) -> str | None:
    if mode == "opponent":
        return opponent
    return my_team


@app.get("/teams")
def list_teams() -> list[str]:
    return db.team_abbrs()


@app.get("/plays")
def list_plays(
    myTeam: str | None = None,
    opponent: str | None = None,
    mode: Literal["self", "opponent"] = "self",
    games: str | None = None,
    week: int | None = None,
    down: int | None = None,
    hasFlag: bool | None = None,
):
    game_ids = _scoped_game_ids(myTeam, opponent, games)
    charged_team = _charged_team(myTeam, opponent, mode)

    p = db.plays().join(db.play_features().select("gameId", "playId", "resolved"), on=["gameId", "playId"], how="left")
    p = p.filter(pl.col("dropBackType").is_not_null() & pl.col("resolved").fill_null(False))
    if game_ids is not None:
        p = p.filter(pl.col("gameId").is_in(game_ids))
    if week is not None:
        g = db.games().select("gameId", "week")
        p = p.join(g, on="gameId", how="left").filter(pl.col("week") == week)
    if down is not None:
        p = p.filter(pl.col("down") == down)

    flag_counts = db.flags().group_by(["gameId", "playId"]).agg(flagCount=pl.col("flagId").len())
    if charged_team:
        flag_counts_team = db.flags().filter(pl.col("team") == charged_team).group_by(["gameId", "playId"]).agg(
            flagCount=pl.col("flagId").len()
        )
        p = p.join(flag_counts_team, on=["gameId", "playId"], how="left")
    else:
        p = p.join(flag_counts, on=["gameId", "playId"], how="left")
    p = p.with_columns(flagCount=pl.col("flagCount").fill_null(0))

    if hasFlag:
        p = p.filter(pl.col("flagCount") > 0)

    out = p.select(
        "gameId", "playId", "down", pl.col("yardsToGo"), pl.col("possessionTeam").alias("offense"),
        pl.col("defensiveTeam").alias("defense"), pl.col("passResult").alias("result"),
        "dropBackType", "flagCount", "playDescription",
    )
    g = db.games().select("gameId", "week")
    out = out.join(g, on="gameId", how="left")
    return out.sort(["gameId", "playId"]).to_dicts()


@app.get("/plays/{game_id}/{play_id}")
def get_play(game_id: int, play_id: int):
    tracking = db.scan_tracking_for_play(game_id, play_id)
    if tracking.height == 0:
        raise HTTPException(status_code=404, detail="play not found")

    play_row = db.plays().filter((pl.col("gameId") == game_id) & (pl.col("playId") == play_id))
    feat_row = db.play_features().filter((pl.col("gameId") == game_id) & (pl.col("playId") == play_id))
    game_row = db.games().filter(pl.col("gameId") == game_id)

    header = {}
    if play_row.height:
        pr = play_row.row(0, named=True)
        gr = game_row.row(0, named=True) if game_row.height else {}
        header = {
            "homeTeam": gr.get("homeTeamAbbr"), "awayTeam": gr.get("visitorTeamAbbr"),
            "quarter": pr.get("quarter"), "clock": pr.get("gameClock"),
            "down": pr.get("down"), "distance": pr.get("yardsToGo"),
            "result": pr.get("passResult"), "coverage": pr.get("pff_passCoverage"),
            "playDescription": pr.get("playDescription"),
            "offense": pr.get("possessionTeam"), "defense": pr.get("defensiveTeam"),
        }

    meta = {}
    if feat_row.height:
        fr = feat_row.row(0, named=True)
        meta = {
            "snapFrameId": fr.get("snapFrameId"), "endOfDropbackFrameId": fr.get("endOfDropbackFrameId"),
            "lineOfScrimmage": fr.get("lineOfScrimmage"), "firstDownX": fr.get("firstDownX"),
        }

    frames = []
    for frame_id, frame_rows in tracking.sort("frameId").group_by("frameId", maintain_order=True):
        objects = [
            {
                "nflId": None if row["isBall"] else row["nflId"],
                "team": row["team"], "jersey": row["jerseyNumber"],
                "x": row["x"], "y": row["y"], "isBall": row["isBall"],
                "role": row.get("pff_role"),
            }
            for row in frame_rows.iter_rows(named=True)
        ]
        frames.append({"frameId": frame_id[0] if isinstance(frame_id, tuple) else frame_id,
                        "event": frame_rows["event"][0], "objects": objects})

    pocket_rows = db.pocket_by_frame().filter((pl.col("gameId") == game_id) & (pl.col("playId") == play_id))
    pocket_by_frame = {int(r["frameId"]): float(r["pocketArea"]) for r in pocket_rows.iter_rows(named=True)}

    play_flags = db.flags().filter((pl.col("gameId") == game_id) & (pl.col("playId") == play_id))
    flags_out = [_flag_to_dict(r) for r in play_flags.iter_rows(named=True)]

    return {"header": header, "meta": meta, "frames": frames, "flags": flags_out, "pocketByFrame": pocket_by_frame}


def _flag_to_dict(row: dict) -> dict:
    return {
        "flagId": row["flagId"], "gameId": row["gameId"], "playId": row["playId"],
        "errorFrameId": row["errorFrameId"], "involvedNflIds": row["involvedNflIds"],
        "team": row["team"], "errorType": row["errorType"], "confidenceLevel": row["confidenceLevel"],
        "explanation": row["explanation"], "epaCost": row["epaCost"],
        "detail": json.loads(row["detail"]) if row["detail"] else {},
    }


@app.get("/flags")
def list_flags(
    myTeam: str | None = None,
    opponent: str | None = None,
    mode: Literal["self", "opponent"] = "self",
    games: str | None = None,
    confidenceLevel: str | None = None,
    errorType: str | None = None,
    player: int | None = None,
    week: int | None = None,
):
    game_ids = _scoped_game_ids(myTeam, opponent, games)
    charged_team = _charged_team(myTeam, opponent, mode)

    f = db.flags()
    if game_ids is not None:
        f = f.filter(pl.col("gameId").is_in(game_ids))
    if charged_team:
        f = f.filter(pl.col("team") == charged_team)
    if confidenceLevel:
        f = f.filter(pl.col("confidenceLevel") == confidenceLevel)
    if errorType:
        f = f.filter(pl.col("errorType") == errorType)
    if player:
        f = f.filter(pl.col("involvedNflIds").list.contains(player))
    if week is not None:
        g = db.games().select("gameId", "week")
        f = f.join(g, on="gameId", how="left").filter(pl.col("week") == week)

    return [_flag_to_dict(r) for r in f.iter_rows(named=True)]


@app.get("/patterns")
def list_patterns(
    myTeam: str | None = None,
    opponent: str | None = None,
    mode: Literal["self", "opponent"] = "self",
    games: str | None = None,
    perspective: Literal["self", "opponent"] | None = None,
):
    game_ids = _scoped_game_ids(myTeam, opponent, games)
    charged_team = _charged_team(myTeam, opponent, mode)
    p = db.patterns()
    if charged_team:
        p = p.filter(pl.col("team") == charged_team)
    if perspective:
        p = p.filter(pl.col("perspective") == perspective)
    p = p.sort("rankScore", descending=True)

    out = []
    for row in p.iter_rows(named=True):
        # playRefs is a list of [gameId, playId] pairs, one per flag in the group.
        play_refs = [{"gameId": pair[0], "playId": pair[1]} for pair in row["playRefs"]]
        out.append(
            {
                "patternId": row["patternId"], "label": f"{row['errorType']} — {row['situationKey']}",
                "team": row["team"], "nflId": row["nflId"], "errorType": row["errorType"],
                "situationKey": row["situationKey"], "perspective": row["perspective"],
                "count": row["count"], "rate": row["rate"], "rateLow90": row["rateLow90"],
                "rateHigh90": row["rateHigh90"], "opportunities": row["opportunities"],
                "sampleSize": row["sampleSize"], "avgCost": row["avgCost"], "rankScore": row["rankScore"],
                "playRefs": play_refs[:20],
            }
        )
    return out


@app.get("/players/{nfl_id}")
def get_player(nfl_id: int, myTeam: str | None = None, opponent: str | None = None, mode: Literal["self", "opponent"] = "self", games: str | None = None):
    game_ids = _scoped_game_ids(myTeam, opponent, games)

    info_row = db.players().filter(pl.col("nflId") == nfl_id)
    info = info_row.row(0, named=True) if info_row.height else {"displayName": "Unknown", "officialPosition": None}

    pm = db.player_measurements().filter(pl.col("nflId") == nfl_id)
    if game_ids is not None:
        pm = pm.filter(pl.col("gameId").is_in(game_ids))

    def _metric(col: str, name: str) -> dict:
        vals = pm[col].drop_nulls() if col in pm.columns else pl.Series([])
        return {"name": name, "value": float(vals.mean()) if vals.len() else None, "sampleSize": int(vals.len())}

    metrics = [
        _metric("getOffTime", "Get-off time (s)"),
        _metric("timeToPressure", "Time to pressure (s)"),
        _metric("depthConceded_1_5", "Depth conceded @1.5s (yd)"),
    ]
    for side in ("inside", "outside"):
        side_rows = pm.filter(pl.col("rushLateralDir") == side)
        n = side_rows.height
        win_rate = float(side_rows["rusherPassedBlocker"].fill_null(False).cast(pl.Int8).mean()) if n else None
        metrics.append({"name": f"Win rate ({side})", "value": win_rate, "sampleSize": n})

    f = db.flags().filter(pl.col("involvedNflIds").list.contains(nfl_id))
    if game_ids is not None:
        f = f.filter(pl.col("gameId").is_in(game_ids))

    p = db.patterns().filter(pl.col("nflId") == nfl_id)

    return {
        "player": {"nflId": nfl_id, "name": info.get("displayName"), "position": info.get("officialPosition")},
        "metrics": metrics,
        "flags": [_flag_to_dict(r) for r in f.iter_rows(named=True)],
        "patterns": p.select("patternId", "errorType", "situationKey", "count", "rate", "rankScore").to_dicts(),
    }


@app.get("/limitations")
def get_limitations():
    return LIMITATIONS
