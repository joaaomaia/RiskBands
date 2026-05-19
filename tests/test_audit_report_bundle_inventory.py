from riskbands.audit_report import _bundle_inventory, build_audit_report_context, render_audit_report_html
from tests.test_audit_report_context import fit_merge_binner


def test_bundle_inventory_contains_audit_report_and_missing_artifact_explanations():
    context = build_audit_report_context(fit_merge_binner())
    inventory = {row["file"]: row for row in context["bundle_inventory"]}

    assert "audit_report.html" in inventory
    assert "missing_decision_log.csv" in inventory
    assert "missing_merge_candidates.csv" in inventory
    assert "Trilha de decisão" in inventory["missing_decision_log.csv"]["purpose"]
    assert "Candidatos avaliados" in inventory["missing_merge_candidates.csv"]["purpose"]


def test_bundle_inventory_does_not_break_before_bundle_is_exported():
    inventory = _bundle_inventory(None)

    assert any(row["file"] == "audit_report.html" for row in inventory)
    assert {row["status"] for row in inventory} <= {"esperado no bundle", "quando disponível"}


def test_bundle_inventory_marks_present_files_when_report_is_inside_bundle(tmp_path):
    binner = fit_merge_binner()
    bundle_dir = tmp_path / "bundle"

    binner.export_bundle(bundle_dir)
    context = build_audit_report_context(binner, bundle_path=bundle_dir)
    inventory = {row["file"]: row for row in context["bundle_inventory"]}
    html = render_audit_report_html(context)

    assert inventory["metadata.json"]["status"] == "presente"
    assert inventory["binnings.json"]["status"] == "presente"
    assert inventory["audit_report.html"]["status"] == "presente"
    assert "metadata.json" in html
    assert "audit_report.html" in html


def test_bundle_inventory_omits_existence_claims_for_missing_optional_files(tmp_path):
    binner = fit_merge_binner()
    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)
    (bundle_dir / "missing_merge_candidates.csv").unlink()

    context = build_audit_report_context(binner, bundle_path=bundle_dir)
    inventory = {row["file"]: row for row in context["bundle_inventory"]}

    assert inventory["missing_merge_candidates.csv"]["status"] != "presente"
