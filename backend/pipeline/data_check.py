"""Phase 0 data check (Requirement 2): event semantics and data-quality
findings, written to reports/data_check.md. Reads the raw CSVs directly —
this runs once, before the Parquet conversion it validates the need for.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from pipeline.config import REPO_ROOT
from pipeline.resolve import resolve_play_frames

RAW_DIR = REPO_ROOT / "data" / "raw"
REPORT_PATH = REPO_ROOT / "reports" / "data_check.md"


def _last_event_per_play(tracking: pl.DataFrame) -> pl.DataFrame:
    with_event = tracking.filter(pl.col("event") != "None")
    return (
        with_event.sort("frameId")
        .group_by(["gameId", "playId"])
        .agg(pl.col("event").last().alias("lastEvent"))
    )


def run_data_check(tracking: pl.DataFrame, plays: pl.DataFrame, pff: pl.DataFrame) -> dict:
    distinct_events = sorted(
        e for e in tracking["event"].unique().to_list() if e and e != "None"
    )
    last_events = _last_event_per_play(tracking)
    last_event_counts = (
        last_events.group_by("lastEvent").len().sort("len", descending=True)
    )

    # Survey every play's resolution via the resolver.
    results = []
    for (game_id, play_id), play_tracking in tracking.group_by(
        ["gameId", "playId"], maintain_order=True
    ):
        r = resolve_play_frames(play_tracking)
        results.append(
            {
                "gameId": game_id,
                "playId": play_id,
                "resolved": r.resolved,
                "unresolvedReason": r.reason,
            }
        )
    resolution_df = pl.DataFrame(
        results,
        schema={"gameId": pl.Int64, "playId": pl.Int64, "resolved": pl.Boolean, "unresolvedReason": pl.Utf8},
    )
    n_plays = resolution_df.height
    n_unresolved = resolution_df.filter(~pl.col("resolved")).height
    unresolved = resolution_df.filter(~pl.col("resolved")).select(
        "gameId", "playId", "unresolvedReason"
    )
    reason_counts = (
        unresolved.group_by("unresolvedReason").len().sort("len", descending=True)
        if n_unresolved
        else pl.DataFrame({"unresolvedReason": [], "len": []})
    )

    missing_rates = {
        "pff_nflIdBlockedPlayer": float(pff["pff_nflIdBlockedPlayer"].is_null().mean()),
        "pff_positionLinedUp": float(pff["pff_positionLinedUp"].is_null().mean()),
    }
    for col in ["x", "y", "s", "a", "dis", "o", "dir"]:
        missing_rates[f"tracking.{col}"] = float(tracking[col].is_null().mean())

    return {
        "distinct_events": distinct_events,
        "last_event_counts": last_event_counts,
        "n_plays": n_plays,
        "n_unresolved": n_unresolved,
        "reason_counts": reason_counts,
        "unresolved": unresolved,
        "missing_rates": missing_rates,
    }


def write_report(findings: dict, path: Path = REPORT_PATH) -> None:
    lines = ["# Phase 0 Data Check", ""]

    lines += ["## Distinct tracking event values", ""]
    for e in findings["distinct_events"]:
        lines.append(f"- `{e}`")
    lines.append("")

    lines += ["## Last recorded event per play", ""]
    lines.append("| Last event | Play count |")
    lines.append("|---|---|")
    for row in findings["last_event_counts"].iter_rows(named=True):
        lines.append(f"| `{row['lastEvent']}` | {row['len']} |")
    lines.append("")

    lines += ["## Snap / end-of-dropback resolution survey", ""]
    lines.append(f"- Total plays surveyed: **{findings['n_plays']}**")
    lines.append(f"- Unresolved plays: **{findings['n_unresolved']}**")
    lines.append("")
    if findings["n_unresolved"]:
        lines.append("### Unresolved reasons")
        lines.append("")
        lines.append("| Reason | Count |")
        lines.append("|---|---|")
        for row in findings["reason_counts"].iter_rows(named=True):
            lines.append(f"| `{row['unresolvedReason']}` | {row['len']} |")
        lines.append("")
        lines.append("### Unresolved plays (gameId, playId, reason)")
        lines.append("")
        lines.append("| gameId | playId | reason |")
        lines.append("|---|---|---|")
        for row in findings["unresolved"].iter_rows(named=True):
            lines.append(f"| {row['gameId']} | {row['playId']} | `{row['unresolvedReason']}` |")
        lines.append("")

    lines += ["## Missing-value rates", ""]
    lines.append("| Field | Missing rate |")
    lines.append("|---|---|")
    for field, rate in findings["missing_rates"].items():
        lines.append(f"| `{field}` | {rate:.2%} |")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def main() -> None:
    # "event" uses the literal string "None" for no-event rows, not a null,
    # so only "NA" is treated as a genuine missing value here.
    tracking = pl.read_csv(RAW_DIR / "tracking" / "*.csv", null_values=["NA"])
    plays = pl.read_csv(RAW_DIR / "plays.csv", null_values=["NA"])
    pff = pl.read_csv(RAW_DIR / "pffScoutingData.csv", null_values=["NA"])

    findings = run_data_check(tracking, plays, pff)
    write_report(findings)
    print(f"Wrote {REPORT_PATH} ({findings['n_plays']} plays, {findings['n_unresolved']} unresolved)")


if __name__ == "__main__":
    main()
