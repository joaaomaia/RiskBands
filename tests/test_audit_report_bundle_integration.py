import json

import pytest

from riskbands import Binner, RiskBands
from tests.test_audit_report_context import fit_merge_binner


def test_public_export_audit_report_method_exists_and_requires_fitted(tmp_path):
    assert hasattr(Binner, "export_audit_report")
    assert hasattr(RiskBands, "export_audit_report")

    with pytest.raises(RuntimeError, match="fitted"):
        RiskBands().export_audit_report(tmp_path / "audit_report.html")


def test_public_export_audit_report_generates_html(tmp_path):
    binner = fit_merge_binner()
    path = tmp_path / "audit_report.html"

    binner.export_audit_report(path, title="Bundle Audit", dataset_name="train")

    text = path.read_text(encoding="utf-8")
    assert "<!doctype html>" in text
    assert "Bundle Audit" in text
    assert "train" in text
    assert "Decisões de merge de missing" in text


def test_export_bundle_old_call_includes_audit_report_and_existing_files(tmp_path):
    binner = fit_merge_binner()
    bundle_dir = tmp_path / "bundle"

    binner.export_bundle(bundle_dir)

    assert (bundle_dir / "audit_report.html").exists()
    for name in [
        "metadata.json",
        "binnings.json",
        "summary.csv",
        "score_details.csv",
        "score_table.csv",
        "audit_table.csv",
        "report.csv",
        "missing_profile.csv",
        "missing_decision_log.csv",
        "missing_merge_candidates.csv",
    ]:
        assert (bundle_dir / name).exists()
    manifest = json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"]["audit_report_html"] == "audit_report.html"


def test_export_bundle_can_disable_audit_report(tmp_path):
    binner = fit_merge_binner()
    bundle_dir = tmp_path / "bundle"

    binner.export_bundle(bundle_dir, include_audit_report=False)

    assert not (bundle_dir / "audit_report.html").exists()
    manifest = json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"]["audit_report_html"] is None
