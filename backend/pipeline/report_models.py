"""Runs both Level 3 models and writes their held-out metrics to
reports/models.md in one place (Requirement 7.10): AUC + calibration for
the pressure model, MAE for the expected-rep model.
"""
from __future__ import annotations

import polars as pl

from pipeline.config import REPO_ROOT
from pipeline.detect import expected_rep, pressure

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
REPORT_PATH = REPO_ROOT / "reports" / "models.md"


def main() -> None:
    rep_metrics = expected_rep.main()
    pressure_metrics = pressure.main()

    # Combine both models' Possible flags into the single flags_level3.parquet
    # that cost.py expects, alongside flags_level1/flags_level2.
    combined = pl.concat([
        pl.read_parquet(PROCESSED_DIR / "flags_level3_rep.parquet"),
        pl.read_parquet(PROCESSED_DIR / "flags_level3_pressure.parquet"),
    ])
    combined.write_parquet(PROCESSED_DIR / "flags_level3.parquet")

    lines = ["# Level 3 Models", "", "## Pressure-probability model", ""]
    lines.append(f"- Held-out AUC: **{pressure_metrics['auc']:.3f}**")
    lines.append(f"- Possible flags (pressure spikes) on held-out games: {pressure_metrics['n_flags']}")
    lines.append("- Calibration (predicted probability bucket -> observed pressure rate):")
    lines.append("")
    lines.append("| Predicted bucket | Observed rate | n |")
    lines.append("|---|---|---|")
    for b in pressure_metrics["calibration"]:
        rate_str = f"{b['rate']:.1%}" if b["rate"] is not None else "n/a"
        lines.append(f"| {b['lo']:.1f}-{b['hi']:.1f} | {rate_str} | {b['n']} |")
    lines.append("")
    lines.append(
        "Frame-level features (min rusher-to-QB distance, rushers within "
        "free_rusher_qb_yd, pocket area, elapsed time, rusher/blocker "
        "counts) are labeled with the play's overall PFF hit/hurry/sack "
        "outcome broadcast to every frame — the tracking data has no "
        "frame-level pressure label, so this is a known simplification."
    )
    lines.append("")
    lines.append("## Expected-rep model (depth conceded at 1.5s)")
    lines.append("")
    lines.append(f"- Baseline (situational averages) MAE: **{rep_metrics['baseline_mae']:.3f} yd**")
    lines.append(f"- LightGBM MAE: **{rep_metrics['gbm_mae']:.3f} yd**")
    lines.append(f"- Held-out reps: {rep_metrics['n_test']}; Possible flags (worse than expected): {rep_metrics['n_flags']}")
    lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines))
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
