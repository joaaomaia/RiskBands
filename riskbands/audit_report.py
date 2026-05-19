"""Standalone narrative audit report for fitted RiskBands binners."""

from __future__ import annotations

import html
import json
import math
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

import numpy as np
import pandas as pd

from .reporting import build_binner_metadata

REPORT_FILENAME = "audit_report.html"
DEFAULT_TITLE = "Relatório de Auditoria do Binning"
DEFAULT_SUBTITLE = (
    "Documento executivo para revisão das configurações, variáveis, decisões sobre valores "
    "ausentes, validações e artefatos do bundle."
)
MAX_CONTEXT_ROWS = 200
AUDIT_LIMITATION_TEXT = (
    "O relatório organiza evidências e decisões técnicas, mas não substitui validação formal "
    "independente nem constitui certificação regulatória."
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return _safe_records(value)
    if isinstance(value, pd.Series):
        return _json_safe(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _safe_records(df: Any, max_rows: int | None = None) -> list[dict[str, Any]]:
    """Return JSON-safe records from a tabular object without non-finite scalars."""
    if df is None:
        return []
    if isinstance(df, pd.DataFrame):
        table = df
    else:
        try:
            table = pd.DataFrame(df)
        except (TypeError, ValueError):
            return []
    if table.empty:
        return []
    if max_rows is not None:
        table = table.head(max_rows)
    return [_json_safe(record) for record in table.to_dict(orient="records")]


def _records_with_warning(
    df: Any,
    *,
    table_name: str,
    warnings: list[str],
    max_rows: int = MAX_CONTEXT_ROWS,
) -> list[dict[str, Any]]:
    length = len(df) if isinstance(df, pd.DataFrame) else 0
    if length > max_rows:
        warnings.append(
            f"Tabela '{table_name}' truncada para {max_rows} linhas no relatório narrativo."
        )
    return _safe_records(df, max_rows=max_rows)


def _safe_table_call(binner: Any, method_name: str, warnings: list[str]) -> pd.DataFrame:
    method = getattr(binner, method_name, None)
    if method is None:
        return pd.DataFrame()
    try:
        result = method()
    except Exception as exc:  # pragma: no cover - defensive best effort
        warnings.append(f"Não foi possível montar '{method_name}': {exc}")
        return pd.DataFrame()
    return result if isinstance(result, pd.DataFrame) else pd.DataFrame()


def _feature_names(binner: Any, binning_table: pd.DataFrame) -> list[str]:
    for attr in ("feature_names_in_", "selected_columns_"):
        value = getattr(binner, attr, None)
        if value:
            return [str(item) for item in value]
    if not binning_table.empty and "variable" in binning_table.columns:
        return [str(item) for item in binning_table["variable"].drop_duplicates().tolist()]
    return []


def _model_config_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "riskbands_version",
        "strategy",
        "score_strategy",
        "missing_policy",
        "effective_missing_policy",
        "missing_merge_criterion",
        "missing_merge_fallback",
        "objective_direction",
        "normalization_strategy",
        "woe_shrinkage_strength",
        "target_name",
        "time_col",
        "features",
        "selected_columns",
        "n_features",
        "input_type",
        "iv_total",
    ]
    return {key: metadata.get(key) for key in keys if key in metadata}


def _merge_criterion_text(criterion: Any) -> str:
    if criterion == "nearest_woe":
        return "WoE mais próximo"
    if criterion == "nearest_event_rate":
        return "event rate mais próximo"
    return str(criterion or "critério configurado")


def _format_distance(row: Mapping[str, Any]) -> str:
    metric = row.get("distance_metric") or row.get("metric") or "distância"
    for key in ("distance", "distance_value", "distance_event_rate", "distance_woe"):
        value = row.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return f"{metric} = {float(value):.6g}"
    return str(metric)


def _decision_action_label(action: str) -> str:
    labels = {
        "missing_merged": "Missing fundido a bin regular",
        "missing_kept_separate": "Fallback para bin separado",
        "no_missing_detected": "Sem missing no fit",
        "separate_bin_created": "Bin separado criado",
        "separate_bin_requested": "Bin separado solicitado",
        "forbidden_missing_detected": "Missing bloqueado",
        "standard_behavior_preserved": "Comportamento standard preservado",
    }
    return labels.get(action, action.replace("_", " ") if action else "Não informado")


def _missing_decision_narrative(row: Mapping[str, Any]) -> str:
    variable = str(row.get("variable") or "variavel")
    action = str(row.get("action") or "")
    criterion = row.get("missing_merge_criterion") or row.get("merge_criterion") or row.get("criterion")
    selected_bin = row.get("selected_bin_label") or row.get("selected_bin")
    fallback = row.get("missing_merge_fallback") or row.get("fallback")

    if action == "missing_merged":
        criterion_text = _merge_criterion_text(criterion)
        return (
            f"Os registros com valor ausente em {variable} foram fundidos ao bin {selected_bin}, "
            f"pois este foi o bin regular com {criterion_text} do grupo missing no conjunto de treino. "
            f"A decisão foi aprendida no fit e reutilizada no transform; o transform não recalcula "
            f"event rate/WoE. Distância registrada: {_format_distance(row)}."
        )
    if action == "missing_kept_separate":
        return (
            f"Os registros ausentes em {variable} permaneceram em bin separado por fallback "
            f"'{fallback or 'separate_bin'}'. A decisão foi aprendida no fit e reaplicada no transform."
        )
    if action == "no_missing_detected":
        return (
            f"Não foram encontrados valores ausentes em {variable} no conjunto de fit. "
            "Nenhum merge de missing foi necessário."
        )
    if action in {"separate_bin_created", "separate_bin_requested"}:
        return (
            f"Valores ausentes em {variable} foram tratados como um grupo separado para manter "
            "a trilha auditável sem imputação opaca."
        )
    if action == "forbidden_missing_detected":
        return (
            f"A política 'forbid' bloqueou valores ausentes em {variable}; a execução deve falhar "
            "quando missing values aparecem nesse contexto."
        )
    if action == "standard_behavior_preserved":
        return (
            f"A política standard preservou o comportamento histórico para {variable}; valores "
            "ausentes seguem a regra padrão aprendida no fit."
        )
    return (
        f"Decisão de missing registrada para {variable}. Consulte os campos técnicos da linha "
        "para detalhes completos."
    )


def _summarize_missing_decisions(binner: Any) -> list[dict[str, Any]]:
    decisions = _safe_records(getattr(binner, "missing_decision_log_", pd.DataFrame()))
    if not decisions:
        return [
            {
                "variable": "todas",
                "action": "no_decision_log",
                "action_label": "Sem trilha de missing registrada",
                "narrative": (
                    "Não há linhas em missing_decision_log_. Isso pode ocorrer quando o modelo "
                    "foi ajustado sem trilha de missing persistida ou quando não houve missing relevante."
                ),
            }
        ]

    enriched = []
    for row in decisions:
        record = dict(row)
        action = str(record.get("action") or "")
        record["action_label"] = _decision_action_label(action)
        record["narrative"] = _missing_decision_narrative(record)
        enriched.append(record)
    return enriched


def _summarize_missing(binner: Any, decisions: list[dict[str, Any]]) -> dict[str, Any]:
    profile = getattr(binner, "missing_profile_", pd.DataFrame())
    candidates = getattr(binner, "missing_merge_candidates_", pd.DataFrame())
    actions = [str(row.get("action") or "") for row in decisions]
    return {
        "missing_policy": getattr(binner, "missing_policy_", getattr(binner, "missing_policy", None)),
        "effective_missing_policy": getattr(binner, "effective_missing_policy_", None),
        "missing_merge_criterion": getattr(binner, "missing_merge_criterion_", None),
        "missing_merge_fallback": getattr(binner, "missing_merge_fallback_", None),
        "profile_rows": int(len(profile)) if isinstance(profile, pd.DataFrame) else 0,
        "decision_rows": len(decisions),
        "candidate_rows": int(len(candidates)) if isinstance(candidates, pd.DataFrame) else 0,
        "merged_decisions": actions.count("missing_merged"),
        "fallback_decisions": actions.count("missing_kept_separate"),
        "no_missing_decisions": actions.count("no_missing_detected"),
    }


def _validation_context(binner: Any) -> dict[str, Any]:
    reports = {
        "fit_validation_report": getattr(binner, "fit_validation_report_", None),
        "transform_validation_report": getattr(binner, "transform_validation_report_", None),
        "validation_report": getattr(binner, "validation_report_", None),
    }
    safe_reports = {key: _json_safe(value) for key, value in reports.items() if value is not None}
    alerts: list[dict[str, Any]] = []
    for report_name, report in safe_reports.items():
        if isinstance(report, Mapping):
            for key, value in report.items():
                key_text = str(key).lower()
                if "warning" in key_text or "alert" in key_text or "error" in key_text:
                    alerts.append({"source": report_name, "field": key, "value": value})
    return {
        "reports": safe_reports,
        "alerts": alerts,
        "has_validation": bool(safe_reports),
    }


def _inventory_specs() -> list[dict[str, str]]:
    return [
        {
            "file": "metadata.json",
            "purpose": "Manifest do bundle, versão, configuração e lista de artefatos.",
            "audience": "governança, auditoria, data science",
            "when": "primeiro arquivo para revisar rastreabilidade do pacote",
        },
        {
            "file": "binnings.json",
            "purpose": "Artefato JSON com metadados e tabelas de binning por variável.",
            "audience": "data science, model risk",
            "when": "comparar ou versionar a configuração técnica",
        },
        {
            "file": "summary.csv",
            "purpose": "Resumo curto por variável.",
            "audience": "negócio técnico, data science",
            "when": "entender rapidamente quais variáveis foram aceitas",
        },
        {
            "file": "score_details.csv",
            "purpose": "Componentes detalhados do score objetivo.",
            "audience": "data science, model risk",
            "when": "explicar por que uma configuração foi selecionada",
        },
        {
            "file": "score_table.csv",
            "purpose": "Tabela de score pronta para revisão.",
            "audience": "data science, auditoria",
            "when": "revisar pesos, score e componentes principais",
        },
        {
            "file": "audit_table.csv",
            "purpose": "Tabela consolidada com cortes, score, penalidades e racional.",
            "audience": "auditoria, model risk",
            "when": "fazer revisão técnica consolidada por variável",
        },
        {
            "file": "report.csv",
            "purpose": "Relatório tabular completo por variável.",
            "audience": "data science",
            "when": "investigar detalhes além do resumo executivo",
        },
        {
            "file": "missing_profile.csv",
            "purpose": "Perfil de volume, evento, event rate e WoE dos missing values.",
            "audience": "model risk, data science",
            "when": "avaliar impacto dos valores ausentes no fit",
        },
        {
            "file": "missing_decision_log.csv",
            "purpose": "Trilha de decisão da política de missing por variável.",
            "audience": "auditoria, model risk",
            "when": "confirmar acao tomada para missing values",
        },
        {
            "file": "missing_merge_candidates.csv",
            "purpose": "Candidatos avaliados quando missing values são fundidos a bins regulares.",
            "audience": "model risk, data science",
            "when": "explicar por que um bin foi escolhido no merge",
        },
        {
            "file": "missing_transform_fallback_log.csv",
            "purpose": "Eventos de fallback no transform quando aplicável.",
            "audience": "data science, auditoria",
            "when": "investigar missing values novos em transformação",
        },
        {
            "file": "feature_tables/",
            "purpose": "Tabelas individuais de binning por variável.",
            "audience": "data science, analistas de crédito",
            "when": "revisar cortes e métricas de uma variável específica",
        },
        {
            "file": REPORT_FILENAME,
            "purpose": "Relatório HTML narrativo e autocontido para auditoria do bundle.",
            "audience": "auditoria, model risk, governança, negócio técnico",
            "when": "ler a explicação executiva, imprimir ou exportar para PDF pelo navegador",
        },
    ]


def _bundle_inventory(
    path: str | Path | None = None,
    *,
    current_report_name: str | None = None,
) -> list[dict[str, Any]]:
    bundle_path = Path(path) if path is not None else None
    manifest_artifacts: dict[str, Any] = {}
    if bundle_path is not None and (bundle_path / "metadata.json").exists():
        try:
            manifest = json.loads((bundle_path / "metadata.json").read_text(encoding="utf-8"))
            artifacts = manifest.get("artifacts", {})
            manifest_artifacts = artifacts if isinstance(artifacts, dict) else {}
        except (OSError, json.JSONDecodeError):
            manifest_artifacts = {}

    inventory = []
    for spec in _inventory_specs():
        filename = spec["file"]
        file_path = bundle_path / filename if bundle_path is not None else None
        is_directory_spec = filename.endswith("/")
        exists = False
        if file_path is not None:
            exists = file_path.exists() if not is_directory_spec else file_path.is_dir()
        if current_report_name and filename == current_report_name:
            exists = True

        manifest_key_present = any(value == filename.rstrip("/") for value in manifest_artifacts.values())
        manifest_key_present = manifest_key_present or any(value == filename for value in manifest_artifacts.values())
        if filename == REPORT_FILENAME and manifest_artifacts.get("audit_report_html") == REPORT_FILENAME:
            manifest_key_present = True

        status = "presente" if exists else "quando disponível"
        if bundle_path is None and filename != REPORT_FILENAME:
            status = "esperado no bundle"
        if not exists and not manifest_key_present and bundle_path is not None:
            status = "não encontrado"

        inventory.append({**spec, "status": status})
    return inventory


def _limitations() -> list[str]:
    return [
        AUDIT_LIMITATION_TEXT,
        "O HTML é autocontido e print-friendly, mas PDF nativo não é obrigatório nesta sprint.",
        "O relatório usa apenas artefatos e atributos já aprendidos; ele não recalcula o modelo.",
        "Validações independentes, políticas internas e revisão regulatória continuam fora deste artefato.",
        "Dados sensíveis ou reais não devem ser inseridos manualmente no relatório.",
    ]


def build_audit_report_context(
    binner: Any,
    *,
    title: str | None = None,
    dataset_name: str | None = None,
    bundle_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a JSON-safe context for the standalone audit narrative report."""
    warnings: list[str] = []
    if hasattr(binner, "_ensure_fitted"):
        binner._ensure_fitted()

    try:
        metadata = build_binner_metadata(binner)
    except Exception as exc:  # pragma: no cover - defensive best effort
        metadata = {}
        warnings.append(f"Não foi possível montar metadados completos: {exc}")

    binning_table = _safe_table_call(binner, "binning_table", warnings)
    summary = _safe_table_call(binner, "summary", warnings)
    score_table = _safe_table_call(binner, "score_table", warnings)
    audit_table = _safe_table_call(binner, "audit_table", warnings)
    report_table = _safe_table_call(binner, "report", warnings)
    features = _feature_names(binner, binning_table)

    binning_tables: dict[str, list[dict[str, Any]]] = {}
    for feature in features:
        try:
            table = binner.binning_table(column=feature)
        except Exception as exc:  # pragma: no cover - defensive best effort
            warnings.append(f"Não foi possível montar binning de '{feature}': {exc}")
            table = pd.DataFrame()
        binning_tables[feature] = _records_with_warning(
            table,
            table_name=f"binning_tables.{feature}",
            warnings=warnings,
        )

    missing_decisions = _summarize_missing_decisions(binner)
    merge_candidates = _records_with_warning(
        getattr(binner, "missing_merge_candidates_", pd.DataFrame()),
        table_name="missing_merge_candidates",
        warnings=warnings,
    )

    context = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": title or DEFAULT_TITLE,
        "dataset_name": dataset_name,
        "language": "pt-BR",
        "metadata": _json_safe(metadata),
        "model_config": _json_safe(_model_config_from_metadata(metadata)),
        "variable_summary": _records_with_warning(
            summary,
            table_name="summary",
            warnings=warnings,
        ),
        "score_table": _records_with_warning(
            score_table,
            table_name="score_table",
            warnings=warnings,
        ),
        "audit_table": _records_with_warning(
            audit_table,
            table_name="audit_table",
            warnings=warnings,
        ),
        "report_table": _records_with_warning(
            report_table,
            table_name="report",
            warnings=warnings,
        ),
        "missing_summary": _json_safe(_summarize_missing(binner, missing_decisions)),
        "missing_profile": _records_with_warning(
            getattr(binner, "missing_profile_", pd.DataFrame()),
            table_name="missing_profile",
            warnings=warnings,
        ),
        "missing_decisions": _json_safe(missing_decisions),
        "merge_candidates": _json_safe(merge_candidates),
        "missing_merge_map": _json_safe(getattr(binner, "missing_merge_map_", {})),
        "binning_tables": _json_safe(binning_tables),
        "validation": _validation_context(binner),
        "bundle_inventory": _bundle_inventory(
            bundle_path,
            current_report_name=REPORT_FILENAME if bundle_path is not None else None,
        ),
        "limitations": _limitations(),
        "warnings": warnings,
        "appendix": {
            "context_contract": [
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
            ],
            "data_sources": [
                "binner fitted attributes",
                "public reporting tables",
                "bundle path inventory when provided",
            ],
        },
    }
    return _json_safe(context)


def _e(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _format_value(value: Any) -> str:
    if value is None:
        return "Não informado"
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (list, dict)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return text if len(text) <= 180 else f"{text[:177]}..."
    return str(value)


def _sao_paulo_timezone() -> timezone:
    if ZoneInfo is not None:
        try:
            return ZoneInfo("America/Sao_Paulo")
        except ZoneInfoNotFoundError:
            pass
    return timezone(timedelta(hours=-3), "São Paulo")


def _format_generated_at(value: Any) -> str:
    if value is None:
        return "Não informado"
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value)
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(_sao_paulo_timezone()).replace(microsecond=0)
    return parsed.strftime("%d/%m/%Y %H:%M São Paulo")


def _render_brand_mark() -> str:
    logo_path = (
        Path(__file__).resolve().parents[1]
        / "docs-site"
        / "public"
        / "brand"
        / "riskbands_horizontal_monochrome.svg"
    )
    try:
        svg = logo_path.read_text(encoding="utf-8").strip()
    except OSError:
        return '<span class="brand-fallback">Gerado por RiskBands</span>'
    svg = svg.replace(' xmlns="http://www.w3.org/2000/svg"', "")
    svg = svg.replace("\ufeff", "")
    if svg.startswith("<?xml"):
        svg = svg[svg.find("?>") + 2 :].lstrip()
    if not svg.startswith("<svg"):
        return '<span class="brand-fallback">Gerado por RiskBands</span>'
    svg = svg.replace(
        "<svg ",
        '<svg class="riskbands-logo" role="img" aria-label="RiskBands" data-riskbands-logo="inline-svg" ',
        1,
    )
    return svg


def _columns(records: list[dict[str, Any]], preferred: list[str] | None = None, *, limit: int = 10) -> list[str]:
    if not records:
        return []
    preferred = preferred or []
    discovered: list[str] = []
    for record in records:
        for key in record:
            if key not in discovered:
                discovered.append(key)
    ordered = [key for key in preferred if key in discovered]
    ordered.extend(key for key in discovered if key not in ordered)
    return ordered[:limit]


def _render_table(
    records: list[dict[str, Any]],
    *,
    preferred: list[str] | None = None,
    empty_message: str = "Sem dados disponíveis.",
    css_class: str = "data-table",
    max_columns: int = 10,
) -> str:
    if not records:
        return f'<p class="muted">{_e(empty_message)}</p>'
    cols = _columns(records, preferred, limit=max_columns)
    head = "".join(f"<th>{_e(col)}</th>" for col in cols)
    rows = []
    for record in records:
        cells = "".join(f"<td>{_e(_format_value(record.get(col)))}</td>" for col in cols)
        row_class = ' class="selected-row"' if record.get("selected") is True else ""
        rows.append(f"<tr{row_class}>{cells}</tr>")
    return (
        '<div class="table-wrap">'
        f'<table class="{css_class}"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
        "</div>"
    )


def _render_key_values(data: Mapping[str, Any]) -> str:
    items = []
    for key, value in data.items():
        items.append(
            '<div class="kv-item">'
            f'<dt>{_e(key.replace("_", " "))}</dt>'
            f"<dd>{_e(_format_value(value))}</dd>"
            "</div>"
        )
    return f'<dl class="kv-grid">{"".join(items)}</dl>'


def _badge(text: Any, tone: str = "neutral") -> str:
    return f'<span class="badge badge-{_e(tone)}">{_e(_format_value(text))}</span>'


def _render_missing_decisions(records: list[dict[str, Any]]) -> str:
    cards = []
    for record in records:
        tone = "success" if record.get("action") == "missing_merged" else "neutral"
        cards.append(
            '<article class="decision-card">'
            f'<div class="decision-title">{_e(record.get("variable"))} {_badge(record.get("action_label"), tone)}</div>'
            f'<p>{_e(record.get("narrative"))}</p>'
            "</article>"
        )
    table = _render_table(
        records,
        preferred=[
            "variable",
            "action",
            "status",
            "selected_bin_label",
            "distance_metric",
            "distance",
            "fallback_used",
        ],
        max_columns=8,
    )
    return "".join(cards) + table


def _render_binning_tables(tables: Mapping[str, list[dict[str, Any]]]) -> str:
    if not tables:
        return '<p class="muted">Sem tabelas de binning disponíveis.</p>'
    sections = []
    for variable, rows in tables.items():
        sections.append(
            '<section class="subsection">'
            f"<h3>{_e(variable)}</h3>"
            + _render_table(
                rows,
                preferred=[
                    "variable",
                    "bin",
                    "bin_label",
                    "count",
                    "event_count",
                    "non_event_count",
                    "event_rate",
                    "woe",
                    "iv",
                ],
                max_columns=9,
            )
            + "</section>"
        )
    return "".join(sections)


def _render_validation(validation: Mapping[str, Any]) -> str:
    if not validation.get("has_validation"):
        return (
            '<div class="callout">'
            "Não há relatório de validação persistido. Use fit/transform com validação quando "
            "precisar registrar checks formais no bundle."
            "</div>"
        )
    alerts = validation.get("alerts") or []
    reports = validation.get("reports") or {}
    return (
        _render_table(alerts, preferred=["source", "field", "value"], empty_message="Sem alertas registrados.")
        + '<details class="technical-details"><summary>Payloads de validação</summary>'
        + f"<pre>{_e(json.dumps(reports, ensure_ascii=False, indent=2))}</pre>"
        + "</details>"
    )


def render_audit_report_html(context: dict[str, Any]) -> str:
    """Render a standalone HTML audit narrative with embedded CSS."""
    title = context.get("title") or DEFAULT_TITLE
    metadata = context.get("metadata") or {}
    model_config = context.get("model_config") or {}
    missing_summary = context.get("missing_summary") or {}
    generated_at = context.get("generated_at")
    dataset_name = context.get("dataset_name")
    variable_summary = context.get("variable_summary") or []
    missing_decisions = context.get("missing_decisions") or []
    merge_candidates = context.get("merge_candidates") or []
    limitations = context.get("limitations") or []
    warnings = context.get("warnings") or []
    inventory = context.get("bundle_inventory") or []
    binning_tables = context.get("binning_tables") or {}
    validation = context.get("validation") or {}
    dataset_display = dataset_name if dataset_name else "Não informada"
    generated_display = _format_generated_at(generated_at)
    version_display = metadata.get("riskbands_version", "não informada")
    missing_policy_display = missing_summary.get("missing_policy", "não informada")
    brand_mark = _render_brand_mark()

    sections = [
        ("summary", "Capa / Resumo executivo"),
        ("how-to-read", "Como ler este relatório"),
        ("config", "Configuração do modelo"),
        ("variables", "Resumo das variáveis"),
        ("missing-policy", "Políticas de missing values"),
        ("missing-merge", "Decisões de merge de missing"),
        ("merge-candidates", "Candidatos avaliados no merge"),
        ("binning", "Binning final por variável"),
        ("validation", "Validação e alertas"),
        ("inventory", "Inventário do bundle"),
        ("limitations", "Limitações conhecidas"),
        ("appendix", "Apêndice técnico"),
    ]
    toc = "".join(f'<li><a href="#{section_id}">{_e(label)}</a></li>' for section_id, label in sections)
    warning_html = "".join(f"<li>{_e(item)}</li>" for item in warnings)
    limitation_html = "".join(f"<li>{_e(item)}</li>" for item in limitations)

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_e(title)}</title>
  <style>
    :root {{
      --ink: #1f2933;
      --muted: #5d6b7a;
      --line: #d8dee6;
      --panel: #ffffff;
      --soft: #f5f7fa;
      --accent: #176b87;
      --accent-2: #b45309;
      --success: #166534;
      --warning: #92400e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--soft);
      color: var(--ink);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 15px;
      line-height: 1.55;
    }}
    .page {{ max-width: 1320px; margin: 0 auto; padding: 28px; box-sizing: border-box; }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 28px;
      margin-bottom: 20px;
      max-width: 100%;
      overflow: hidden;
      box-sizing: border-box;
    }}
    .hero-top {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
    }}
    .hero-copy {{ min-width: 0; flex: 1 1 auto; }}
    .hero-copy p {{ max-width: 780px; margin: 0; color: var(--muted); }}
    .hero-brand {{
      flex: 0 0 auto;
      display: flex;
      align-items: flex-start;
      justify-content: flex-end;
      min-width: 128px;
    }}
    .riskbands-logo {{
      display: block;
      width: 128px;
      max-width: 100%;
      height: auto;
    }}
    .brand-fallback {{
      display: inline-block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    h1, h2, h3 {{ color: #18212f; line-height: 1.2; margin: 0 0 12px; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 22px; border-bottom: 2px solid var(--line); padding-bottom: 8px; }}
    h3 {{ font-size: 17px; margin-top: 18px; }}
    a {{ color: var(--accent); text-decoration: none; }}
    .meta-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
    .badge {{
      display: inline-block;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 10px;
      font-size: 12px;
      font-weight: 700;
      background: #eef4f7;
    }}
    .badge-success {{ color: var(--success); background: #ecfdf3; border-color: #bbf7d0; }}
    .badge-neutral {{ color: var(--ink); background: #eef2f7; }}
    .section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
      margin: 18px 0;
      break-inside: avoid;
      max-width: 100%;
      overflow: hidden;
      box-sizing: border-box;
    }}
    .subsection {{ margin-top: 18px; max-width: 100%; box-sizing: border-box; }}
    .toc {{
      columns: 2;
      padding-left: 22px;
      margin: 10px 0 0;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin: 16px 0;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fbfcfe;
    }}
    .metric-label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .metric-card strong {{ display: block; font-size: 30px; color: var(--accent); margin-top: 4px; }}
    .metric-helper {{ display: block; color: var(--muted); font-size: 12px; margin-top: 4px; }}
    .kv-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
      margin: 0;
    }}
    .kv-item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: #fbfcfe;
    }}
    dt {{ color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    dd {{ margin: 3px 0 0; overflow-wrap: anywhere; }}
    .table-wrap {{
      width: 100%;
      max-width: 100%;
      overflow-x: auto;
      box-sizing: border-box;
      margin-top: 12px;
    }}
    .data-table {{
      width: max-content;
      min-width: 100%;
      max-width: none;
      border-collapse: collapse;
      font-size: 13px;
      table-layout: auto;
      box-sizing: border-box;
    }}
    th {{
      border: 1px solid var(--line);
      padding: 8px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
      word-break: normal;
      overflow-wrap: normal;
    }}
    td {{
      border: 1px solid var(--line);
      padding: 8px;
      text-align: left;
      vertical-align: top;
      white-space: normal;
      word-break: normal;
      overflow-wrap: anywhere;
    }}
    th {{ background: #eef2f7; font-weight: 700; }}
    tr.selected-row td {{ background: #fff7ed; border-color: #fed7aa; }}
    .decision-card {{
      border-left: 5px solid var(--accent);
      background: #f8fbfd;
      padding: 12px 14px;
      margin: 12px 0;
    }}
    .decision-title {{ font-weight: 700; margin-bottom: 6px; }}
    .callout {{
      border: 1px solid #f1c27d;
      border-left: 5px solid var(--accent-2);
      background: #fff8ed;
      border-radius: 8px;
      padding: 12px 14px;
      margin: 12px 0;
    }}
    .muted {{ color: var(--muted); }}
    .technical-details summary {{ cursor: pointer; font-weight: 700; margin-top: 10px; }}
    pre {{
      white-space: pre-wrap;
      border: 1px solid var(--line);
      background: #f8fafc;
      padding: 12px;
      overflow-wrap: anywhere;
    }}
    .report-footer {{
      color: var(--muted);
      font-size: 12px;
      text-align: center;
      padding: 18px 8px 4px;
    }}
    @media (max-width: 720px) {{
      .hero-top {{ flex-direction: column; }}
      .hero-brand {{ justify-content: flex-start; min-width: 0; }}
      .riskbands-logo {{ width: 118px; }}
    }}
    @media print {{
      body {{ background: #ffffff; color: #000000; font-size: 11pt; }}
      .page {{ max-width: none; padding: 0; }}
      .hero, .section {{ border-color: #bbbbbb; box-shadow: none; break-inside: avoid; }}
      .hero-top {{ display: flex; align-items: flex-start; justify-content: space-between; }}
      .riskbands-logo {{ width: 120px; }}
      .table-wrap {{ overflow: visible; max-width: 100%; }}
      .data-table {{ width: 100%; min-width: 0; font-size: 9.5pt; table-layout: auto; }}
      th, td {{ padding: 5px; white-space: normal; word-break: normal; overflow-wrap: anywhere; }}
      a {{ color: #000000; text-decoration: none; }}
      table {{ break-inside: auto; page-break-inside: auto; }}
      tr {{ break-inside: avoid; page-break-inside: avoid; }}
      h2, h3 {{ break-after: avoid; page-break-after: avoid; }}
      .toc {{ columns: 1; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header id="summary" class="hero">
      <div class="hero-top">
        <div class="hero-copy">
          <h1>{_e(title)}</h1>
          <p>{_e(DEFAULT_SUBTITLE)}</p>
        </div>
        <div class="hero-brand">{brand_mark}</div>
      </div>
      <div class="meta-row">
        {_badge("Base: " + str(dataset_display))}
        {_badge("Gerado em: " + str(generated_display))}
        {_badge("Versão RiskBands: " + str(version_display))}
        {_badge("Política de missing: " + str(missing_policy_display))}
      </div>
      <div class="cards">
        <div class="metric-card">
          <span class="metric-label">Variáveis analisadas</span>
          <strong>{_e(len(binning_tables))}</strong>
          <span class="metric-helper">Total de variáveis ajustadas no fit</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Decisões sobre ausentes</span>
          <strong>{_e(len(missing_decisions))}</strong>
          <span class="metric-helper">Registros de política ou merge de missing</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Candidatos avaliados</span>
          <strong>{_e(len(merge_candidates))}</strong>
          <span class="metric-helper">Bins regulares considerados para merge</span>
        </div>
      </div>
      <div class="callout">{_e(AUDIT_LIMITATION_TEXT)}</div>
    </header>

    <section id="how-to-read" class="section">
      <h2>Como ler este relatório</h2>
      <p>
        Comece pelo resumo executivo, revise a configuração do modelo e avance para as seções de
        missing values quando houver valores ausentes. Linhas destacadas em candidatos de merge indicam
        o bin selecionado no fit. Este HTML é adequado para impressão/exportação para PDF pelo navegador.
      </p>
      <ol class="toc">{toc}</ol>
    </section>

    <section id="config" class="section">
      <h2>Configuração do modelo</h2>
      {_render_key_values(model_config)}
    </section>

    <section id="variables" class="section">
      <h2>Resumo das variáveis</h2>
      {_render_table(variable_summary, preferred=["variable", "n_bins", "iv", "score", "objective_score"])}
    </section>

    <section id="missing-policy" class="section">
      <h2>Políticas de missing values</h2>
      <p>
        Missing policy define como valores ausentes são tratados. Event rate é a proporção de eventos
        em um bin. WoE mede a separação entre eventos e não eventos. IV resume poder informativo.
        Fallback é a regra usada quando a decisão principal não pode ser aplicada.
      </p>
      {_render_key_values(missing_summary)}
      <h3>Perfil de missing</h3>
      {_render_table(
        context.get("missing_profile") or [],
        preferred=["variable", "bin_label", "n_missing_fit", "event_rate", "woe", "merge_status"],
      )}
    </section>

    <section id="missing-merge" class="section">
      <h2>Decisões de merge de missing</h2>
      {_render_missing_decisions(missing_decisions)}
    </section>

    <section id="merge-candidates" class="section">
      <h2>Candidatos avaliados no merge</h2>
      <p>
        Esta tabela mostra os bins regulares avaliados para receber o grupo missing. A linha destacada
        representa o candidato selecionado no fit.
      </p>
      {_render_table(
        merge_candidates,
        preferred=[
            "variable",
            "criterion",
            "candidate_rank",
            "candidate_bin_label",
            "candidate_event_rate",
            "candidate_woe",
            "distance_event_rate",
            "distance_woe",
            "selected",
        ],
      )}
    </section>

    <section id="binning" class="section">
      <h2>Binning final por variável</h2>
      {_render_binning_tables(binning_tables)}
    </section>

    <section id="validation" class="section">
      <h2>Validação e alertas</h2>
      {_render_validation(validation)}
      {"<ul>" + warning_html + "</ul>" if warning_html else '<p class="muted">Sem avisos internos de renderização.</p>'}
    </section>

    <section id="inventory" class="section">
      <h2>Inventário do bundle</h2>
      {_render_table(inventory, preferred=["file", "status", "purpose", "audience", "when"], max_columns=5)}
    </section>

    <section id="limitations" class="section">
      <h2>Limitações conhecidas</h2>
      <ul>{limitation_html}</ul>
    </section>

    <section id="appendix" class="section">
      <h2>Apêndice técnico</h2>
      <p>
        Binning é o agrupamento de valores em faixas ou categorias. O relatório usa contexto JSON-safe
        derivado do binner fitted e dos artefatos de bundle quando disponíveis.
      </p>
      <details class="technical-details">
        <summary>Metadados completos</summary>
        <pre>{_e(json.dumps(metadata, ensure_ascii=False, indent=2))}</pre>
      </details>
    </section>
    <footer class="report-footer">
      Relatório gerado automaticamente. Revise as evidências e políticas internas antes de uso em processos formais.
    </footer>
  </main>
</body>
</html>
"""


def export_audit_report_html(
    binner: Any,
    path: str | Path,
    *,
    title: str | None = None,
    dataset_name: str | None = None,
    bundle_path: str | Path | None = None,
) -> Path:
    """Write the standalone audit narrative HTML report as UTF-8."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    resolved_bundle_path = bundle_path
    if resolved_bundle_path is None and (target.parent / "metadata.json").exists():
        resolved_bundle_path = target.parent
    context = build_audit_report_context(
        binner,
        title=title,
        dataset_name=dataset_name,
        bundle_path=resolved_bundle_path,
    )
    target.write_text(render_audit_report_html(context), encoding="utf-8")
    return target
