"""Level 3 expected-rep model (Requirement 7.1, 7.2): a situational-average
baseline, then a LightGBM upgrade, predicting depth conceded at 1.5s and
probability of being beaten by 2.5s per engagement. Possible flags fire
when a rep is far worse than predicted.
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import polars as pl

from pipeline.config import REPO_ROOT, Thresholds
from pipeline.detect.flag import clamp_to_play, new_flag
from pipeline.detect.split import leakage_free_player_history, shrink_toward_group, train_test_split_by_game

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
MODELS_DIR = REPO_ROOT / "models"

FEATURE_COLS = ["rusherCount", "blockerCount", "down", "yardsToGo", "shrunkHistory"]


def build_rep_table(
    player_measurements: pl.DataFrame,
    engagements: pl.DataFrame,
    play_features: pl.DataFrame,
    plays: pl.DataFrame,
) -> pl.DataFrame:
    """One row per blocker-engagement rep: outcome columns + raw context
    features (history is attached separately, per split, to avoid leakage)."""
    blockers = player_measurements.filter(pl.col("closestApproachDist").is_null()).select(
        "gameId", "playId", "nflId", "depthConceded_1_5"
    )
    primary = (
        engagements.sort("minDistance")
        .group_by(["gameId", "playId", "blockerNflId"])
        .agg(rusherNflId=pl.col("rusherNflId").first())
        .rename({"blockerNflId": "nflId"})
    )
    rushers_beaten = player_measurements.filter(pl.col("closestApproachDist").is_not_null()).select(
        "gameId", "playId", pl.col("nflId").alias("rusherNflId"), "rusherPassedBlocker"
    )

    rep = blockers.join(primary, on=["gameId", "playId", "nflId"], how="left")
    rep = rep.join(rushers_beaten, on=["gameId", "playId", "rusherNflId"], how="left")
    rep = rep.join(
        play_features.select("gameId", "playId", "rusherCount", "blockerCount"), on=["gameId", "playId"], how="left"
    )
    rep = rep.join(plays.select("gameId", "playId", "down", "yardsToGo"), on=["gameId", "playId"], how="left")
    rep = rep.filter(pl.col("depthConceded_1_5").is_not_null())
    rep = rep.with_columns(beaten=pl.col("rusherPassedBlocker").fill_null(False).cast(pl.Int8))
    return rep


def attach_shrunk_history(
    rep: pl.DataFrame, train_game_ids: set[int], rep_threshold: int
) -> pl.DataFrame:
    hist = leakage_free_player_history(
        rep.rename({"nflId": "playerId"}).select(pl.col("playerId").alias("nflId"), "gameId", "depthConceded_1_5"),
        train_game_ids,
        "depthConceded_1_5",
    )
    rep = rep.join(hist.select("nflId", "playerMean", "groupMean", "reps"), on="nflId", how="left")
    overall_mean = hist["playerMean"].mean() or 0.0
    rep = rep.with_columns(
        groupMean=pl.col("groupMean").fill_null(overall_mean),
    ).with_columns(
        playerMean=pl.col("playerMean").fill_null(pl.col("groupMean")),
        reps=pl.col("reps").fill_null(0),
    )
    shrunk = [
        shrink_toward_group(pm, gm, int(r), rep_threshold)
        for pm, gm, r in zip(rep["playerMean"].to_list(), rep["groupMean"].to_list(), rep["reps"].to_list())
    ]
    return rep.with_columns(shrunkHistory=pl.Series(shrunk))


def train_baseline(train: pl.DataFrame) -> pl.DataFrame:
    """Situational-average baseline (Requirement 7.2): mean depth conceded
    per (rusherCount, blockerCount, down) on training games, established
    before any GBM."""
    return train.group_by(["rusherCount", "blockerCount", "down"]).agg(
        baselineDepth=pl.col("depthConceded_1_5").mean()
    )


def train_gbm(train: pl.DataFrame) -> lgb.Booster:
    X = train.select(FEATURE_COLS).fill_null(0).to_numpy()
    y = train["depthConceded_1_5"].to_numpy()
    dataset = lgb.Dataset(X, label=y, feature_name=FEATURE_COLS)
    params = {"objective": "regression", "verbosity": -1, "num_leaves": 15, "min_data_in_leaf": 20}
    return lgb.train(params, dataset, num_boost_round=100)


def emit_flags(
    test: pl.DataFrame,
    model: lgb.Booster,
    residual_sigma: float,
    residual_std: float,
    plays_resolved: pl.DataFrame,
    bounds: pl.DataFrame,
) -> list[dict]:
    X = test.select(FEATURE_COLS).fill_null(0).to_numpy()
    predicted = model.predict(X)
    residual = test["depthConceded_1_5"].to_numpy() - predicted
    test = test.with_columns(predicted=pl.Series(predicted), residual=pl.Series(residual))

    flagged = test.filter(pl.col("residual") > residual_sigma * residual_std)
    flagged = flagged.join(
        plays_resolved.select("gameId", "playId", "snapFrameId", "endOfDropbackFrameId", pl.col("possessionTeam").alias("offense")),
        on=["gameId", "playId"], how="left",
    )
    flagged = flagged.join(bounds, on=["gameId", "playId"], how="left")

    flags = []
    for row in flagged.iter_rows(named=True):
        if row["snapFrameId"] is None:
            continue
        error_frame = clamp_to_play(int(row["endOfDropbackFrameId"]), int(row["snapFrameId"]), int(row["lastFrameId"]))
        involved = [int(row["nflId"])]
        if row["rusherNflId"] is not None:
            involved.append(int(row["rusherNflId"]))
        flags.append(
            new_flag(
                game_id=row["gameId"], play_id=row["playId"], error_frame_id=error_frame,
                involved_nfl_ids=involved, team=row["offense"] or "UNK", error_type="worse_than_expected_rep",
                confidence_level="Possible",
                explanation="Possible: film to review: this blocker conceded far more depth than expected for this situation.",
                detail={
                    "model": "expected_rep_lgbm", "predicted": round(float(row["predicted"]), 3),
                    "actual": round(float(row["depthConceded_1_5"]), 3),
                },
            )
        )
    return flags


def main() -> None:
    from pipeline.config import load_thresholds
    from pipeline.features import _dropback_frame

    thresholds = load_thresholds()
    player_measurements = pl.read_parquet(PROCESSED_DIR / "player_measurements.parquet")
    engagements = pl.read_parquet(PROCESSED_DIR / "engagements.parquet")
    play_features = pl.read_parquet(PROCESSED_DIR / "play_features.parquet")
    plays = pl.read_parquet(PROCESSED_DIR / "plays.parquet")
    tracking_norm = pl.read_parquet(PROCESSED_DIR / "tracking_norm.parquet")
    plays_resolved = _dropback_frame()
    bounds = tracking_norm.group_by(["gameId", "playId"]).agg(lastFrameId=pl.col("frameId").max())

    rep = build_rep_table(player_measurements, engagements, play_features, plays)
    train_games, test_games = train_test_split_by_game(rep["gameId"].unique().to_list(), test_frac=0.2)

    rep = attach_shrunk_history(rep, train_games, thresholds.level3.rep_threshold)
    train = rep.filter(pl.col("gameId").is_in(list(train_games)))
    test = rep.filter(pl.col("gameId").is_in(list(test_games)))

    baseline = train_baseline(train)
    model = train_gbm(train)

    X_train = train.select(FEATURE_COLS).fill_null(0).to_numpy()
    train_residual = train["depthConceded_1_5"].to_numpy() - model.predict(X_train)
    residual_std = float(np.std(train_residual))

    flags = emit_flags(test, model, thresholds.level3.rep_residual_sigma, residual_std, plays_resolved, bounds)

    MODELS_DIR.mkdir(exist_ok=True)
    model.save_model(str(MODELS_DIR / "expected_rep.txt"))

    X_test = test.select(FEATURE_COLS).fill_null(0).to_numpy()
    test_predicted = model.predict(X_test)
    test_actual = test["depthConceded_1_5"].to_numpy()
    mae = float(np.mean(np.abs(test_actual - test_predicted)))

    baseline_pred = test.join(baseline, on=["rusherCount", "blockerCount", "down"], how="left")["baselineDepth"]
    baseline_mae = float(np.mean(np.abs(test_actual - baseline_pred.fill_null(test_actual.mean()).to_numpy())))

    from pipeline.detect.flag import flags_to_dataframe

    flags_to_dataframe(flags).write_parquet(PROCESSED_DIR / "flags_level3_rep.parquet")
    print(
        f"Expected-rep: baseline MAE={baseline_mae:.3f}, GBM MAE={mae:.3f} "
        f"(held out {test.height} reps, {len(flags)} Possible flags)"
    )
    return {"baseline_mae": baseline_mae, "gbm_mae": mae, "n_test": test.height, "n_flags": len(flags)}


if __name__ == "__main__":
    main()
