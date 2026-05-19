import json

import numpy as np
import pandas as pd

from riskbands import RiskBands
from riskbands.audit_report import _safe_records, build_audit_report_context


def make_merge_frame(*, with_missing=True):
    score = []
    target = []
    for value, event_rate in [(-5.0, 0.05), (-3.0, 0.20), (0.0, 0.50), (3.0, 0.80), (5.0, 0.95)]:
        n = 30
        events = int(n * event_rate)
        score.extend([value] * n)
        target.extend([1] * events + [0] * (n - events))
    if with_missing:
        score.extend([np.nan] * 30)
        target.extend([1] * 15 + [0] * 15)
    return pd.DataFrame({"score": score, "target": target})


def fit_merge_binner(*, criterion="nearest_event_rate", with_missing=True):
    df = make_merge_frame(with_missing=with_missing)
    binner = RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion=criterion,
    )
    return binner.fit(df, y="target", column="score")


def test_audit_report_context_has_required_json_safe_fields():
    binner = fit_merge_binner()

    context = build_audit_report_context(binner, title="Audit", dataset_name="synthetic")

    assert {
        "metadata",
        "model_config",
        "variable_summary",
        "missing_summary",
        "missing_decisions",
        "merge_candidates",
        "binning_tables",
        "validation",
        "bundle_inventory",
        "limitations",
    } <= set(context)
    assert context["title"] == "Audit"
    assert context["dataset_name"] == "synthetic"
    assert context["language"] == "pt-BR"
    json.dumps(context, ensure_ascii=False)


def test_audit_report_context_summarizes_missing_merge_event_rate():
    binner = fit_merge_binner(criterion="nearest_event_rate")

    context = build_audit_report_context(binner)
    decision = context["missing_decisions"][0]

    assert context["missing_summary"]["missing_policy"] == "merge"
    assert decision["action"] == "missing_merged"
    assert "event rate mais próximo" in decision["narrative"]
    assert "aprendida no fit" in decision["narrative"]
    assert "transform não recalcula event rate/WoE" in decision["narrative"]
    assert any(row["selected"] is True for row in context["merge_candidates"])


def test_audit_report_context_summarizes_missing_merge_nearest_woe():
    binner = fit_merge_binner(criterion="nearest_woe")

    context = build_audit_report_context(binner)
    decision = context["missing_decisions"][0]

    assert decision["action"] == "missing_merged"
    assert "WoE mais próximo" in decision["narrative"]


def test_audit_report_context_handles_no_missing_and_empty_decision_log():
    binner = fit_merge_binner(with_missing=False)
    context = build_audit_report_context(binner)

    assert context["missing_decisions"][0]["action"] == "no_missing_detected"

    binner.missing_decision_log_ = pd.DataFrame()
    context = build_audit_report_context(binner)

    assert context["missing_decisions"][0]["action"] == "no_decision_log"
    json.dumps(context, ensure_ascii=False)


def test_audit_report_context_fallback_narrative_is_explicit():
    binner = fit_merge_binner()
    binner.missing_decision_log_ = pd.DataFrame(
        [
            {
                "variable": "score",
                "action": "missing_kept_separate",
                "status": "kept_separate",
                "missing_merge_fallback": "separate_bin",
                "fallback_used": True,
            }
        ]
    )

    context = build_audit_report_context(binner)

    assert "fallback" in context["missing_decisions"][0]["narrative"].lower()
    assert context["missing_summary"]["fallback_decisions"] == 1


def test_safe_records_normalizes_empty_and_non_finite_values():
    records = _safe_records(
        pd.DataFrame(
            {
                "a": [1.0, np.nan, np.inf, -np.inf],
                "b": [pd.NA, "ok", pd.Timestamp("2026-05-19"), None],
            }
        ),
        max_rows=3,
    )

    assert len(records) == 3
    assert records[1]["a"] is None
    assert records[2]["a"] is None
    assert records[0]["b"] is None
    json.dumps(records, ensure_ascii=False)
