import pandas as pd

from riskbands import RiskBands


def profile_row(*, n, events, label="bin"):
    event_rate = events / n if n else 0.0
    std_error = (event_rate * (1 - event_rate) / n) ** 0.5 if n else 0.0
    return {
        "variable": "score",
        "bin_label": label,
        "n": n,
        "events": events,
        "non_events": n - events,
        "event_rate": event_rate,
        "event_rate_std_error": std_error,
        "share": 1.0,
    }


def compare_status(reference, application):
    binner = RiskBands()
    alerts = binner._event_rate_profile_alerts(
        pd.DataFrame([application]),
        pd.DataFrame([reference]),
    )
    assert len(alerts) == 1
    return alerts[0]


def test_small_delta_with_large_samples_is_ok():
    alert = compare_status(
        profile_row(n=10_000, events=1_000),
        profile_row(n=10_000, events=1_030),
    )

    assert alert["status"] == "ok"


def test_large_delta_with_large_samples_is_warning_or_critical():
    alert = compare_status(
        profile_row(n=10_000, events=1_000),
        profile_row(n=10_000, events=3_000),
    )

    assert alert["status"] in {"warning", "critical"}
    assert "possible_population_drift" in alert["alert_flags"]


def test_large_delta_with_small_reference_is_insufficient_reference_sample():
    alert = compare_status(
        profile_row(n=10, events=1),
        profile_row(n=10_000, events=3_000),
    )

    assert alert["status"] == "insufficient_reference_sample"


def test_few_reference_events_recommends_increasing_sample_size():
    alert = compare_status(
        profile_row(n=1_000, events=1),
        profile_row(n=1_000, events=100),
    )

    assert alert["status"] == "insufficient_events"
    assert "increasing sample_size" in alert["recommendation"]


def test_few_application_events_is_insufficient_application_sample():
    alert = compare_status(
        profile_row(n=1_000, events=100),
        profile_row(n=25, events=1),
    )

    assert alert["status"] == "insufficient_application_sample"


def test_target_missing_is_reported_as_target_missing():
    binner = RiskBands()
    report = binner._build_transform_validation_report(
        application_profile=None,
        target_available=False,
        backend="pandas",
    )

    assert report["status"] == "skipped"
    assert report["reason"] == "target_not_available"


def test_real_drift_simulation_flags_possible_population_drift():
    alert = compare_status(
        profile_row(n=5_000, events=500),
        profile_row(n=5_000, events=1_250),
    )

    assert alert["status"] in {"warning", "critical"}
    assert "possible_population_drift" in alert["alert_flags"]
