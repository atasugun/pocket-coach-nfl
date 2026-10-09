"""Calibrate Level 2 against Level 1 (the answer key) and write
reports/level2_calibration.md (Requirement 6.7, 6.8). Thresholds themselves
are tuned by hand in config/thresholds.yaml against the training split;
this module reports precision/recall of the resulting rules on the held-out
split only. The lost_escape_lane rule has no PFF label that can confirm it,
so it is reported as "no answer key" and validated by manual film review
instead.
"""
from __future__ import annotations

import json

import polars as pl

from pipeline.config import REPO_ROOT
from pipeline.detect.split import train_test_split_by_game

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
REPORT_PATH = REPO_ROOT / "reports" / "level2_calibration.md"

# Which Level 1 error types count as "ground truth positive" for each
# Level 2 rule's play-level precision/recall check.
RULE_TO_GROUND_TRUTH = {
    "free_rusher": ["sack_allowed", "hit_allowed", "hurry_allowed", "beaten_by_defender"],
    "wasted_double_team": ["sack_allowed", "hit_allowed", "hurry_allowed", "beaten_by_defender"],
    "stunt_not_handled": ["sack_allowed", "hit_allowed", "hurry_allowed", "beaten_by_defender"],
}
NO_ANSWER_KEY_RULES = {"lost_escape_lane"}


def _precision_recall(l2_plays: set[tuple[int, int]], l1_plays: set[tuple[int, int]], all_plays: set[tuple[int, int]]) -> dict:
    tp = len(l2_plays & l1_plays)
    fp = len(l2_plays - l1_plays)
    fn = len(l1_plays - l2_plays)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall}


def calibrate(flags_l1: pl.DataFrame, flags_l2: pl.DataFrame, held_out_games: set[int]) -> dict:
    results = {}
    l2_held = flags_l2.filter(pl.col("gameId").is_in(list(held_out_games)))
    l1_held = flags_l1.filter(pl.col("gameId").is_in(list(held_out_games)))

    for rule in sorted(flags_l2["errorType"].unique().to_list()):
        rule_flags = l2_held.filter(pl.col("errorType") == rule)
        l2_plays = set(zip(rule_flags["gameId"].to_list(), rule_flags["playId"].to_list()))

        if rule in NO_ANSWER_KEY_RULES:
            results[rule] = {"no_answer_key": True, "n_flags": len(l2_plays)}
            continue

        gt_types = RULE_TO_GROUND_TRUTH.get(rule, [])
        gt_flags = l1_held.filter(pl.col("errorType").is_in(gt_types))
        l1_plays = set(zip(gt_flags["gameId"].to_list(), gt_flags["playId"].to_list()))
        all_plays = l2_plays | l1_plays
        results[rule] = {"no_answer_key": False, **_precision_recall(l2_plays, l1_plays, all_plays)}

    return results


def write_report(results: dict, n_train_games: int, n_test_games: int, path=REPORT_PATH) -> None:
    lines = ["# Level 2 Calibration", ""]
    lines.append(
        f"Thresholds tuned on the training split ({n_train_games} games); "
        f"precision/recall below is computed on the held-out split only ({n_test_games} games)."
    )
    lines.append("")
    lines.append("| Rule | Precision | Recall | TP | FP | FN |")
    lines.append("|---|---|---|---|---|---|")
    for rule, r in results.items():
        if r.get("no_answer_key"):
            lines.append(f"| `{rule}` | no answer key | no answer key | — | — | {r['n_flags']} flags, manual review |")
        else:
            p = f"{r['precision']:.1%}" if r["precision"] is not None else "n/a"
            rec = f"{r['recall']:.1%}" if r["recall"] is not None else "n/a"
            lines.append(f"| `{rule}` | {p} | {rec} | {r['tp']} | {r['fp']} | {r['fn']} |")
    lines.append("")
    lines.append(
        "`lost_escape_lane` has no PFF label that can confirm a defensive "
        "containment breakdown, so it is validated by manual review of a "
        "sample of flagged plays instead of against PFF labels (Requirement 6.8)."
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def main() -> None:
    flags_l1 = pl.read_parquet(PROCESSED_DIR / "flags_level1.parquet")
    flags_l2 = pl.read_parquet(PROCESSED_DIR / "flags_level2.parquet")

    all_game_ids = sorted(set(flags_l2["gameId"].to_list()) | set(flags_l1["gameId"].to_list()))
    train_games, test_games = train_test_split_by_game(all_game_ids, test_frac=0.2)

    results = calibrate(flags_l1, flags_l2, test_games)
    write_report(results, len(train_games), len(test_games))
    print(f"Wrote {REPORT_PATH}: {json.dumps({k: v for k, v in results.items()}, default=str)}")


if __name__ == "__main__":
    main()
