"""Generate a standalone audit report and bundle for a small synthetic dataset."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from riskbands import RiskBands


def make_audit_report_demo_dataset() -> pd.DataFrame:
    score = []
    target = []
    for value, event_rate in [(-5.0, 0.05), (-3.0, 0.20), (0.0, 0.50), (3.0, 0.80), (5.0, 0.95)]:
        n = 30
        events = int(n * event_rate)
        score.extend([value] * n)
        target.extend([1] * events + [0] * (n - events))

    score.extend([np.nan] * 30)
    target.extend([1] * 15 + [0] * 15)
    return pd.DataFrame({"score": score, "target": target})


def run_audit_bundle_report_demo(output_dir: str | Path | None = None) -> dict[str, Path | pd.DataFrame]:
    if output_dir is None:
        output_dir = Path(__file__).resolve().parents[1] / "_tmp_riskbands_bundle_smoke" / "audit_report_demo"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = make_audit_report_demo_dataset()
    binner = RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    )
    binner.fit(df, y="target", column="score")

    audit_report_path = output_dir / "audit_report.html"
    bundle_dir = output_dir / "bundle"

    binner.export_audit_report(
        audit_report_path,
        title="Relatório de Auditoria do Binning",
        dataset_name="synthetic_credit_demo",
    )
    binner.export_bundle(bundle_dir)

    return {
        "dataset": df,
        "audit_report_path": audit_report_path,
        "bundle_dir": bundle_dir,
        "bundle_audit_report_path": bundle_dir / "audit_report.html",
        "missing_decision_log": binner.missing_decision_log_,
        "missing_merge_candidates": binner.missing_merge_candidates_,
    }


def main() -> None:
    results = run_audit_bundle_report_demo()
    print(f"audit_report: {results['audit_report_path']}")
    print(f"bundle_dir: {results['bundle_dir']}")
    print(f"bundle_audit_report: {results['bundle_audit_report_path']}")


if __name__ == "__main__":
    main()
