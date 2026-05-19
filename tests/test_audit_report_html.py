import re
from pathlib import Path

from riskbands.audit_report import (
    AUDIT_LIMITATION_TEXT,
    build_audit_report_context,
    export_audit_report_html,
    render_audit_report_html,
)
from tests.test_audit_report_context import fit_merge_binner


def test_audit_report_html_contains_contract_sections_and_embedded_css():
    html = render_audit_report_html(build_audit_report_context(fit_merge_binner()))

    assert html.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in html
    assert "<style>" in html
    assert "@media print" in html
    assert "Relatório de Auditoria do Binning" in html
    for section in [
        "Capa / Resumo executivo",
        "Como ler este relatório",
        "Configuração do modelo",
        "Resumo das variáveis",
        "Políticas de missing values",
        "Decisões de merge de missing",
        "Candidatos avaliados no merge",
        "Binning final por variável",
        "Validação e alertas",
        "Inventário do bundle",
        "Limitações conhecidas",
        "Apêndice técnico",
    ]:
        assert section in html


def test_audit_report_html_is_standalone_and_contains_required_limitations():
    html = render_audit_report_html(build_audit_report_context(fit_merge_binner()))

    assert "D:\\" not in html
    assert "http://" not in html
    assert "https://" not in html
    assert AUDIT_LIMITATION_TEXT in html
    assert "certificação regulatória" in html
    assert "não promete conformidade regulatória" not in html.lower()
    assert "adequado para impressão/exportação para PDF pelo navegador" in html
    assert "data-riskbands-logo=\"inline-svg\"" in html or "Gerado por RiskBands" in html


def test_audit_report_html_uses_executive_header_cards_and_friendly_metadata():
    context = build_audit_report_context(fit_merge_binner())
    context["generated_at"] = "2026-05-19T19:41:21.821661+00:00"
    html = render_audit_report_html(context)

    assert "Relatório de Auditoria do Binning" in html
    assert "Documento executivo para revisão das configurações" in html
    assert "Variáveis analisadas" in html
    assert "Total de variáveis ajustadas no fit" in html
    assert "Decisões sobre ausentes" in html
    assert "Candidatos avaliados" in html
    assert "Base: Não informada" in html
    generated_badge = re.search(r"Gerado em: ([^<]+)</span>", html)
    assert generated_badge is not None
    assert generated_badge.group(1) == "19/05/2026 16:41 São Paulo"
    assert "UTC" not in generated_badge.group(1)
    assert "2026-05-19T19:41:21.821661+00:00" not in html
    assert "821661" not in html
    assert "Versão RiskBands:" in html
    assert "Política de missing: merge" in html


def test_audit_report_html_contains_missing_merge_narrative_and_selected_candidate():
    html = render_audit_report_html(build_audit_report_context(fit_merge_binner()))

    assert "aprendida no fit" in html
    assert "transform não recalcula event rate/WoE" in html
    assert "selected-row" in html
    assert "Candidatos avaliados no merge" in html


def test_audit_report_tables_are_wrapped_for_responsive_layout():
    html = render_audit_report_html(build_audit_report_context(fit_merge_binner()))

    table_count = html.count("<table")
    wrapped_table_count = len(re.findall(r'<div class="table-wrap"><table', html))

    assert table_count >= 5
    assert wrapped_table_count == table_count
    assert ".table-wrap" in html
    assert "overflow-x: auto" in html
    assert "max-width: 1320px" in html
    assert "max-width: 100%" in html
    assert "width: max-content" in html
    assert "min-width: 100%" in html
    assert "box-sizing: border-box" in html
    assert "white-space: nowrap" in html
    assert "word-break: normal" in html
    assert "overflow-wrap: anywhere" in html
    assert "@media print" in html
    assert "http://" not in html
    assert "https://" not in html


def test_export_audit_report_html_writes_utf8_without_mojibake(tmp_path):
    path = tmp_path / "audit_report.html"

    export_audit_report_html(fit_merge_binner(), path)
    text = path.read_text(encoding="utf-8")

    assert "Relatório de Auditoria do Binning" in text
    assert "Configuração" in text
    assert "variáveis" in text
    assert "Decisões" in text
    assert "Validação" in text
    assert "Limitações" in text
    assert "O relatório organiza evidências" in text
    for bad in ("\u00c3", "\u00c2", "\ufffd"):
        assert bad not in text


def test_export_audit_report_html_accepts_path_objects(tmp_path):
    path = Path(tmp_path) / "nested" / "audit_report.html"

    returned = export_audit_report_html(fit_merge_binner(), path)

    assert returned == path
    assert path.exists()
