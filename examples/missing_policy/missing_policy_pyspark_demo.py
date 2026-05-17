"""Small optional PySpark demo for RiskBands missing policies."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from riskbands import RiskBands


FEATURES = ["score", "rating"]


def _configure_local_spark_environment() -> None:
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

    if os.name == "nt" and not os.environ.get("JAVA_HOME"):
        for candidate in [
            Path("C:/Program Files/Microsoft/jdk-21.0.1.12-hotspot"),
            Path("C:/Program Files/Java/jdk-22"),
        ]:
            if (candidate / "bin" / "java.exe").exists():
                os.environ["JAVA_HOME"] = str(candidate)
                break


def _spark_imports():
    try:
        from pyspark.sql import SparkSession, types as T
    except ImportError:
        print(
            "PySpark is not installed. Install the optional extra with "
            '`pip install "riskbands[spark]"` to run this demo.'
        )
        return None, None

    return SparkSession, T


def _make_spark_frame(spark, types_module):
    rows = [
        (410.0, "A", 0),
        (450.0, "A", 0),
        (480.0, "B", 0),
        (None, "B", 1),
        (520.0, None, 0),
        (560.0, "C", 1),
        (590.0, "C", 0),
        (630.0, "D", 1),
        (None, "D", 1),
        (680.0, None, 1),
        (710.0, "E", 1),
        (750.0, "E", 0),
    ] * 4
    schema = types_module.StructType(
        [
            types_module.StructField("score", types_module.DoubleType(), True),
            types_module.StructField("rating", types_module.StringType(), True),
            types_module.StructField("target", types_module.IntegerType(), False),
        ]
    )
    return spark.createDataFrame(rows, schema=schema)


def _show(title: str, value: object) -> None:
    print(f"\n=== {title} ===")
    print(value)


def run_pyspark_missing_policy_demo() -> dict[str, object]:
    """Run a small local Spark example, returning skip status when unavailable."""

    _configure_local_spark_environment()
    SparkSession, T = _spark_imports()
    if SparkSession is None or T is None:
        return {"skipped": True, "reason": "pyspark is not installed"}

    spark_tmp = Path(".pytest_tmp/spark_missing_policy_demo")
    spark_tmp.mkdir(parents=True, exist_ok=True)

    spark = (
        SparkSession.builder.master("local[2]")
        .appName("riskbands-missing-policy-demo")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.local.dir", str(spark_tmp.resolve()))
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    try:
        sdf = _make_spark_frame(spark, T)
        binner = RiskBands(
            max_bins=4,
            min_event_rate_diff=0.0,
            force_categorical=["rating"],
            missing_policy="separate_bin",
            sample_size=1000,
        )
        binner.fit(sdf, y="target", columns=FEATURES, validate=True)
        transformed = binner.transform(
            sdf.select(*FEATURES),
            columns=FEATURES,
            validate=True,
        )
        transformed_preview = transformed.limit(8).toPandas()

        try:
            RiskBands(
                max_bins=4,
                min_event_rate_diff=0.0,
                force_categorical=["rating"],
                missing_policy="forbid",
            ).fit(sdf, y="target", columns=FEATURES)
        except ValueError as exc:
            forbid_fit_error = str(exc)
        else:  # pragma: no cover - this would mean the policy contract changed.
            forbid_fit_error = "UNEXPECTED: forbid did not fail on Spark missing data."

        return {
            "skipped": False,
            "transformed_preview": transformed_preview,
            "missing_profile": binner.missing_profile_.copy(),
            "missing_decision_log": binner.missing_decision_log_.copy(),
            "forbid_fit_error": forbid_fit_error,
        }
    finally:
        spark.stop()


def main() -> None:
    results = run_pyspark_missing_policy_demo()
    if results["skipped"]:
        _show("PySpark demo skipped", results["reason"])
        return

    _show("separate_bin transformed preview", results["transformed_preview"])
    _show("separate_bin missing_profile_", results["missing_profile"])
    _show("separate_bin missing_decision_log_", results["missing_decision_log"])
    _show("forbid fit error", results["forbid_fit_error"])


if __name__ == "__main__":
    main()
