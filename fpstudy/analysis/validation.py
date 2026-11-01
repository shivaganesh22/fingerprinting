"""Validation tooling for precision, recall, F1, and stratified sampling of ground truth."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

from fpstudy.storage.store import DataStore


def calculate_binary_metrics(
    y_true: list[int],
    y_pred: list[int],
) -> dict[str, Any]:
    """Calculate precision, recall, F1 score, and confusion matrix from ground truth and predictions."""
    if len(y_true) != len(y_pred):
        raise ValueError("Ground truth and prediction lengths must match")

    tp = sum(1 for yt, yp in zip(y_true, y_pred, strict=False) if yt == 1 and yp == 1)
    fp = sum(1 for yt, yp in zip(y_true, y_pred, strict=False) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred, strict=False) if yt == 1 and yp == 0)
    tn = sum(1 for yt, yp in zip(y_true, y_pred, strict=False) if yt == 0 and yp == 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(y_true) if len(y_true) > 0 else 0.0

    return {
        "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "accuracy": accuracy,
        "total_samples": len(y_true),
    }


class ValidationTooling:
    """Manages stratified sampling for human review and evaluation against hand labels."""

    def __init__(self, store: DataStore):
        self.store = store

    def generate_stratified_sample(
        self,
        run_id: str,
        output_csv_path: Path | str = "data/labelled/validation_sample_template.csv",
        evidence_json_path: Path | str = "data/labelled/validation_evidence.json",
        sample_size: int = 100,
        random_seed: int = 42,
    ) -> Path:
        """Sample scripts/sites stratified across flagged vs non-flagged and dump evidence for labelling."""
        successful_visit_ids = {
            visit["visit_id"] for visit in self.store.get_visits(run_id) if visit["status"] == "ok"
        }
        classifications = [
            row
            for row in self.store.get_classifications_for_run(run_id)
            if row["visit_id"] in successful_visit_ids
        ]
        if not classifications:
            raise ValueError(f"No classifications from successful visits found for run {run_id}")

        import random

        rng = random.Random(random_seed)

        flagged = [c for c in classifications if c["flagged"] == 1]
        unflagged = [c for c in classifications if c["flagged"] == 0]

        n_flagged = min(len(flagged), sample_size // 2)
        n_unflagged = min(len(unflagged), sample_size - n_flagged)

        sampled_flagged = rng.sample(flagged, n_flagged) if flagged else []
        sampled_unflagged = rng.sample(unflagged, n_unflagged) if unflagged else []
        combined = sampled_flagged + sampled_unflagged
        rng.shuffle(combined)

        out_csv = Path(output_csv_path)
        out_csv.parent.mkdir(parents=True, exist_ok=True)

        # Write CSV template for student annotation
        fieldnames = [
            "sample_id",
            "domain",
            "script_url",
            "vector",
            "predicted_flag",
            "confidence",
            "ground_truth_label",  # 1 for fingerprinting, 0 for benign
            "notes",
        ]
        evidence_dump = {}

        with out_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for idx, item in enumerate(combined, 1):
                s_id = f"samp_{idx:03d}"
                writer.writerow(
                    {
                        "sample_id": s_id,
                        "domain": item["domain"],
                        "script_url": item["script_url"],
                        "vector": item["vector"],
                        "predicted_flag": item["flagged"],
                        "confidence": item["confidence"],
                        "ground_truth_label": "",  # To be annotated by student
                        "notes": "",
                    }
                )
                evidence_dump[s_id] = {
                    "domain": item["domain"],
                    "script_url": item["script_url"],
                    "vector": item["vector"],
                    "predicted_flag": item["flagged"],
                    "evidence": json.loads(item["evidence"])
                    if isinstance(item["evidence"], str)
                    else item["evidence"],
                }

        out_ev = Path(evidence_json_path)
        out_ev.parent.mkdir(parents=True, exist_ok=True)
        out_ev.write_text(json.dumps(evidence_dump, indent=2), encoding="utf-8")

        return out_csv

    def evaluate_labels(self, labels_csv_path: Path | str) -> dict[str, Any]:
        """Evaluate classifier predictions against student-annotated ground truth."""
        path = Path(labels_csv_path)
        if not path.is_file():
            raise FileNotFoundError(f"Labelled CSV file not found: {path}")

        df = pd.read_csv(path)
        # Filter rows where ground_truth_label is provided
        df_valid = df.dropna(subset=["ground_truth_label"])
        df_valid = df_valid[df_valid["ground_truth_label"].astype(str).str.strip().isin(["0", "1"])]

        if df_valid.empty:
            return {
                "error": "No annotated ground truth labels found (values must be 0 or 1)",
                "total_rows": len(df),
            }

        y_true = df_valid["ground_truth_label"].astype(int).tolist()
        y_pred = df_valid["predicted_flag"].astype(int).tolist()

        overall_metrics = calculate_binary_metrics(y_true, y_pred)

        # Per-vector evaluation
        per_vector = {}
        for vec in df_valid["vector"].unique():
            sub = df_valid[df_valid["vector"] == vec]
            yt = sub["ground_truth_label"].astype(int).tolist()
            yp = sub["predicted_flag"].astype(int).tolist()
            per_vector[vec] = calculate_binary_metrics(yt, yp)

        return {
            "overall": overall_metrics,
            "per_vector": per_vector,
            "evaluated_count": len(df_valid),
            "total_annotated": len(df),
        }
