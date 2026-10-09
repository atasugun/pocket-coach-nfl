"""Level 3 pressure-probability model (Requirement 7.3, 7.4): per-frame
probability the play ends in pressure, trained on PFF hit/hurry/sack
labels. A pressure spike (rise >= pressure_spike_delta within a sliding
pressure_spike_window) emits a Possible flag attributed to the blocker
nearest the causing rusher.

Frame-level features are aggregated from positions/speeds of rushers,
blockers, and the QB; the label is play-level (did the play end in
pressure) broadcast to every frame of that play — a known simplification,
documented in reports/models.md, since the tracking data has no frame-level
pressure label to train against directly.
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import polars as pl

from pipeline.config import REPO_ROOT
from pipeline.detect.flag import clamp_to_play, flags_to_dataframe, new_flag
from pipeline.detect.split import train_test_split_by_game

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
MODELS_DIR = REPO_ROOT / "models"

FEATURE_COLS = [
    "minRusherToQbDist", "nRushersWithinFreeYd", "pocketArea", "elapsed", "nRushers", "nBlockers",
]


def build_frame_features(
    window: pl.DataFrame, pocket_by_frame: pl.DataFrame, play_features: pl.DataFrame, free_rusher_qb_yd: float
) -> pl.DataFrame:
    qb = window.filter(pl.col("pff_role") == "Pass").select(
        "gameId", "playId", "frameId", pl.col("x").alias("qbx"), pl.col("y").alias("qby")
    )
    rushers = window.filter(pl.col("pff_role") == "Pass Rush").join(qb, on=["gameId", "playId", "frameId"], how="inner")
    rushers = rushers.with_columns(
        distToQb=((pl.col("x") - pl.col("qbx")) ** 2 + (pl.col("y") - pl.col("qby")) ** 2).sqrt()
    )
    per_frame = rushers.group_by(["gameId", "playId", "frameId"]).agg(
        minRusherToQbDist=pl.col("distToQb").min(),
        nRushersWithinFreeYd=(pl.col("distToQb") <= free_rusher_qb_yd).sum(),
    )
    per_frame = per_frame.join(pocket_by_frame, on=["gameId", "playId", "frameId"], how="left")
    per_frame = per_frame.join(
        window.select("gameId", "playId", "frameId", "snapFrameId").unique(), on=["gameId", "playId", "frameId"], how="left"
    )
    per_frame = per_frame.with_columns(elapsed=(pl.col("frameId") - pl.col("snapFrameId")) / 10.0)
    per_frame = per_frame.join(
        play_features.select("gameId", "playId", pl.col("rusherCount").alias("nRushers"), pl.col("blockerCount").alias("nBlockers")),
        on=["gameId", "playId"], how="left",
    )
    return per_frame


def main() -> None:
    from pipeline.config import load_thresholds
    from pipeline.features import _dropback_frame, _windowed_tracking

    thresholds = load_thresholds()
    tracking_norm = pl.read_parquet(PROCESSED_DIR / "tracking_norm.parquet")
    play_features = pl.read_parquet(PROCESSED_DIR / "play_features.parquet")
    pocket_by_frame = pl.read_parquet(PROCESSED_DIR / "pocket_by_frame.parquet")
    pff = pl.read_parquet(PROCESSED_DIR / "pff_scouting.parquet")

    plays_resolved = _dropback_frame()
    window = _windowed_tracking(tracking_norm, plays_resolved)

    frame_features = build_frame_features(window, pocket_by_frame, play_features, thresholds.level2.free_rusher_qb_yd)

    had_pressure = (
        pff.with_columns(pressured=(pl.col("pff_hit") == 1) | (pl.col("pff_hurry") == 1) | (pl.col("pff_sack") == 1))
        .group_by(["gameId", "playId"]).agg(label=pl.col("pressured").any().cast(pl.Int8))
    )
    frame_features = frame_features.join(had_pressure, on=["gameId", "playId"], how="left")
    frame_features = frame_features.drop_nulls(FEATURE_COLS + ["label"])

    train_games, test_games = train_test_split_by_game(frame_features["gameId"].unique().to_list(), test_frac=0.2)
    train = frame_features.filter(pl.col("gameId").is_in(list(train_games)))
    test = frame_features.filter(pl.col("gameId").is_in(list(test_games)))

    X_train = train.select(FEATURE_COLS).to_numpy()
    y_train = train["label"].to_numpy()
    dataset = lgb.Dataset(X_train, label=y_train, feature_name=FEATURE_COLS)
    params = {"objective": "binary", "verbosity": -1, "num_leaves": 15, "min_data_in_leaf": 50}
    model = lgb.train(params, dataset, num_boost_round=100)

    MODELS_DIR.mkdir(exist_ok=True)
    model.save_model(str(MODELS_DIR / "pressure.txt"))

    X_test = test.select(FEATURE_COLS).to_numpy()
    y_test = test["label"].to_numpy()
    test_pred = model.predict(X_test)

    auc = _auc(y_test, test_pred)

    test = test.with_columns(prob=pl.Series(test_pred)).sort(["gameId", "playId", "frameId"])
    flags = detect_pressure_spikes(
        test, thresholds.level3.pressure_spike_delta, thresholds.level3.pressure_spike_window,
        window, plays_resolved, tracking_norm,
    )
    flags_to_dataframe(flags).write_parquet(PROCESSED_DIR / "flags_level3_pressure.parquet")

    print(f"Pressure model AUC={auc:.3f} on {test.select('gameId','playId').unique().height} held-out plays; {len(flags)} spike flags")
    return calibration_bins(auc, test_pred, y_test) | {"n_flags": len(flags)}


def _auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    order = np.argsort(y_score)
    y_true_sorted = y_true[order]
    n_pos = y_true_sorted.sum()
    n_neg = len(y_true_sorted) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = np.argsort(np.argsort(y_score))
    sum_ranks_pos = ranks[y_true == 1].sum()
    auc = (sum_ranks_pos - n_pos * (n_pos - 1) / 2) / (n_pos * n_neg)
    return float(auc)


def detect_pressure_spikes(
    test_with_prob: pl.DataFrame,
    delta: float,
    window_frames: int,
    window: pl.DataFrame,
    plays_resolved: pl.DataFrame,
    tracking_norm: pl.DataFrame,
) -> list[dict]:
    bounds = tracking_norm.group_by(["gameId", "playId"]).agg(lastFrameId=pl.col("frameId").max())
    plays_meta = plays_resolved.select("gameId", "playId", "snapFrameId", pl.col("possessionTeam").alias("offense"))

    blockers_at_frame = window.filter(pl.col("pff_role") == "Pass Block").select(
        "gameId", "playId", "frameId", pl.col("nflId").alias("blockerNflId"), "x", "y"
    )
    rushers_at_frame = window.filter(pl.col("pff_role") == "Pass Rush").select(
        "gameId", "playId", "frameId", pl.col("nflId").alias("rusherNflId"), pl.col("x").alias("rx"), pl.col("y").alias("ry")
    )

    flags = []
    for (game_id, play_id), g in test_with_prob.group_by(["gameId", "playId"], maintain_order=True):
        probs = g["prob"].to_list()
        frames = g["frameId"].to_list()
        for i in range(len(probs)):
            window_start = max(0, i - window_frames + 1)
            if probs[i] - min(probs[window_start : i + 1]) >= delta:
                spike_frame = frames[i]
                meta = plays_meta.filter((pl.col("gameId") == game_id) & (pl.col("playId") == play_id))
                b = bounds.filter((pl.col("gameId") == game_id) & (pl.col("playId") == play_id))
                if meta.height == 0 or b.height == 0:
                    break
                error_frame = clamp_to_play(int(spike_frame), int(meta["snapFrameId"][0]), int(b["lastFrameId"][0]))

                rushers_here = rushers_at_frame.filter(
                    (pl.col("gameId") == game_id) & (pl.col("playId") == play_id) & (pl.col("frameId") == spike_frame)
                )
                blockers_here = blockers_at_frame.filter(
                    (pl.col("gameId") == game_id) & (pl.col("playId") == play_id) & (pl.col("frameId") == spike_frame)
                )
                involved = []
                if rushers_here.height and blockers_here.height:
                    rr = rushers_here.row(0, named=True)
                    nearest = blockers_here.with_columns(
                        d=((pl.col("x") - rr["rx"]) ** 2 + (pl.col("y") - rr["ry"]) ** 2).sqrt()
                    ).sort("d")
                    involved = [int(nearest["blockerNflId"][0]), int(rr["rusherNflId"])]

                flags.append(
                    new_flag(
                        game_id=game_id, play_id=play_id, error_frame_id=error_frame,
                        involved_nfl_ids=involved, team=meta["offense"][0] or "UNK", error_type="pressure_spike",
                        confidence_level="Possible",
                        explanation="Possible: film to review: modeled pressure probability spiked sharply here.",
                        detail={"model": "pressure_lgbm", "deltaProb": round(probs[i] - min(probs[window_start : i + 1]), 3)},
                    )
                )
                break  # one spike flag per play is enough signal
    return flags


def calibration_bins(auc: float, test_pred: np.ndarray, y_test: np.ndarray) -> dict:
    bins = np.linspace(0, 1, 6)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (test_pred >= lo) & (test_pred < hi)
        n = int(mask.sum())
        rate = float(y_test[mask].mean()) if n else None
        rows.append({"lo": float(lo), "hi": float(hi), "rate": rate, "n": n})
    return {"auc": auc, "calibration": rows}


if __name__ == "__main__":
    main()
