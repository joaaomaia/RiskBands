# Audit Bundle Narrative Report

RiskBands can generate a standalone HTML narrative report for audit, model risk,
governance, data science, credit analysts, and technical business users.

The report is written as:

```text
audit_report.html
```

It is self-contained, uses embedded CSS, does not require internet access, and
does not use external JavaScript or CDN assets.

## How to Generate

Standalone report:

```python
binner.export_audit_report(
    "audit_report.html",
    title="Relatório de Auditoria do Binning",
    dataset_name="train",
)
```

Full bundle with report:

```python
binner.export_bundle("riskbands_bundle")
```

`export_bundle(...)` includes `riskbands_bundle/audit_report.html` by default.
Use `include_audit_report=False` only when the bundle must stay limited to the
previous JSON/CSV artifacts:

```python
binner.export_bundle("riskbands_bundle", include_audit_report=False)
```

## What It Contains

The HTML report includes:

- executive summary;
- how to read the report;
- model configuration;
- variable summary;
- missing value policies;
- missing merge decisions;
- merge candidates evaluated during fit;
- final binning by variable;
- validation and alerts;
- bundle inventory;
- known limitations;
- technical appendix.

For `missing_policy="merge"`, the report explains the learned fit-time decision,
the selected destination bin, the criterion (`nearest_event_rate` or
`nearest_woe`), candidate distances, and the fact that `transform(...)` reuses
the learned decision instead of recalculating event rate or WoE on application
data.

For Spark sampled-to-pandas fit, the report also surfaces the sampling caveat,
source/sample row counts when available, source profile status, and
`missing_sampling_diagnostics`. These fields help reviewers distinguish a merge
decision learned on the sample from evidence observed on the full Spark source.

## Bundle Inventory

The report explains common bundle files, including:

- `metadata.json`;
- `binnings.json`;
- `summary.csv`;
- `score_details.csv`;
- `score_table.csv`;
- `audit_table.csv`;
- `report.csv`;
- `missing_profile.csv`;
- `missing_decision_log.csv`;
- `missing_merge_candidates.csv`;
- sampling diagnostics when Spark sampled-to-pandas fit produced them;
- `feature_tables/`;
- `audit_report.html`.

When generated inside a bundle, the report marks files that are physically
present. Optional files are described only as available when present or when the
bundle manifest lists them.

## PDF Boundary

Native PDF export is not required in this sprint and no heavy PDF dependency is
added. Use the browser print dialog to print or export the HTML report to PDF.

The report organizes evidence and technical decisions, but it does not replace
independent formal validation and does not constitute regulatory certification.

## Example

See:

```text
examples/audit_report/audit_bundle_report_demo.py
```

The example creates a small synthetic dataset, fits `missing_policy="merge"`
with `missing_merge_criterion="nearest_event_rate"`, writes a standalone
`audit_report.html`, and exports a bundle containing `audit_report.html`.
