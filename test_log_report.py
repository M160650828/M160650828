"""Simple test log/report helper for robustness tests.

Provides a minimal API to record test results and write a JSON report.
"""
from __future__ import annotations

import json
import os
import datetime
from typing import List, Dict, Any


class TestLogReport:
    def __init__(self, out_dir: str = "logs"):
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)
        self.session = {
            "started_at": datetime.datetime.utcnow().isoformat() + "Z",
            "results": [],
        }

    def log_result(self, name: str, status: str, message: str = "") -> None:
        entry = {
            "name": name,
            "status": status,
            "message": message,
            "time": datetime.datetime.utcnow().isoformat() + "Z",
        }
        self.session["results"].append(entry)

    def write_report(self, filename: str | None = None) -> str:
        if filename is None:
            ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            filename = f"robust_test_report_{ts}.json"
        path = os.path.join(self.out_dir, filename)
        self.session["finished_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.session, f, ensure_ascii=False, indent=2)
        return path


def simple_run_example():
    rl = TestLogReport()
    rl.log_result("example", "passed", "example run")
    print("Wrote sample report:", rl.write_report())


if __name__ == "__main__":
    simple_run_example()
