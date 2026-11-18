"""B-13 回放一致性校验器的单测。

这些用例证明：校验器能区分「同一数据集的同一结果」与「漂移、缺字段、换数据集」，
从而让「回放与在线一致」这条验收在拿到运行实例之前就能先立住口径。
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from tools.b13_check_replay import compare  # noqa: E402


def load_pair() -> tuple[dict, dict]:
    base = ROOT / "data" / "samples" / "b13"
    online = json.loads((base / "online-result.example.json").read_text("utf-8"))
    replay = json.loads((base / "replay-manifest.example.json").read_text("utf-8"))
    return online, replay


class TestReplayCheck(unittest.TestCase):
    def test_identical_results_pass(self) -> None:
        online, replay = load_pair()
        report = compare(online, replay)
        self.assertTrue(report["ok"])
        self.assertEqual([], report["diffs"])

    def test_float_within_tolerance_passes(self) -> None:
        online, replay = load_pair()
        replay = copy.deepcopy(replay)
        replay["metrics"]["density"] = 0.1123 + 5e-7
        self.assertTrue(compare(online, replay, tol=1e-6)["ok"])

    def test_float_beyond_tolerance_fails(self) -> None:
        online, replay = load_pair()
        replay = copy.deepcopy(replay)
        replay["metrics"]["density"] = 0.1130
        report = compare(online, replay, tol=1e-6)
        self.assertFalse(report["ok"])
        self.assertEqual("metric_float", report["diffs"][0]["kind"])
        self.assertEqual("density", report["diffs"][0]["metric"])

    def test_integer_drift_fails(self) -> None:
        online, replay = load_pair()
        replay = copy.deepcopy(replay)
        replay["metrics"]["risk_count"] = 5
        report = compare(online, replay)
        self.assertFalse(report["ok"])
        self.assertEqual("metric_int", report["diffs"][0]["kind"])

    def test_dataset_hash_mismatch_fails(self) -> None:
        online, replay = load_pair()
        replay = copy.deepcopy(replay)
        replay["dataset"]["sha256"] = "0" * 64
        report = compare(online, replay)
        self.assertFalse(report["ok"])
        self.assertIn("dataset_hash", [d["kind"] for d in report["diffs"]])

    def test_missing_metric_fails(self) -> None:
        online, replay = load_pair()
        replay = copy.deepcopy(replay)
        del replay["metrics"]["handover_items"]
        report = compare(online, replay)
        self.assertFalse(report["ok"])
        self.assertEqual("metric_missing", report["diffs"][0]["kind"])

    def test_evidence_whitespace_is_normalized(self) -> None:
        online, replay = load_pair()
        replay = copy.deepcopy(replay)
        replay["evidence"] = [" ".join(x.split()) for x in replay["evidence"]]
        self.assertTrue(compare(online, replay)["ok"])

    def test_evidence_order_matters(self) -> None:
        online, replay = load_pair()
        replay = copy.deepcopy(replay)
        replay["evidence"] = list(reversed(replay["evidence"]))
        report = compare(online, replay)
        self.assertFalse(report["ok"])
        self.assertEqual("evidence", report["diffs"][0]["kind"])

    def test_tool_version_mismatch_is_reported(self) -> None:
        online, replay = load_pair()
        replay = copy.deepcopy(replay)
        replay["tool"]["prompt"] = "extract-v2"
        report = compare(online, replay)
        self.assertFalse(report["ok"])
        self.assertIn("tool_prompt", [d["kind"] for d in report["diffs"]])


if __name__ == "__main__":
    unittest.main()
