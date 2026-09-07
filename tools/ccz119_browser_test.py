"""Run the one approved offline browser test without installing dependencies."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_PATH = "work/ccz142_current_candidate_read_entry_r01/test_entry_browser.py"
EXPECTED_CASES = 8  # Two checks, desktop/mobile, with/without JavaScript.
TIMEOUT_SECONDS = 180


def _environment() -> dict[str, str]:
    # Retain browser cache/OS locations, never inherited pytest flags or API keys.
    allowed = (
        "PATH",
        "HOME",
        "TMPDIR",
        "TEMP",
        "TMP",
        "SYSTEMROOT",
        "WINDIR",
        "LANG",
        "LC_ALL",
        "PLAYWRIGHT_BROWSERS_PATH",
    )
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    env["UV_OFFLINE"] = "1"
    return env


def _preflight() -> dict:
    # Validate the fixed local HTML and pinned copies before any browser starts.
    checker_path = ROOT / Path(TEST_PATH).parent / "self_check.py"
    spec = importlib.util.spec_from_file_location(
        "ccz119_offline_entry_check", checker_path
    )
    if spec is None or spec.loader is None:
        return {"status": "FAILED", "reason": "STATIC_CHECKER_UNAVAILABLE"}
    try:
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        checker.check_entry(checker_path.parent)
    except Exception as exc:
        return {
            "status": "FAILED",
            "reason": "OFFLINE_FILES_INVALID",
            "detail": str(exc),
        }
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.split(".")[0] == "playwright":
            return {"status": "NOT_DISPATCHED", "reason": "PLAYWRIGHT_MISSING"}
        return {
            "status": "FAILED",
            "reason": "PLAYWRIGHT_IMPORT_FAILED",
            "detail": str(exc),
        }
    except ImportError as exc:
        return {
            "status": "FAILED",
            "reason": "PLAYWRIGHT_IMPORT_FAILED",
            "detail": str(exc),
        }
    try:
        with sync_playwright() as playwright:
            executable = (
                shutil.which("chromium")
                or shutil.which("chromium-browser")
                or playwright.chromium.executable_path
            )
            if not Path(executable).is_file():
                return {"status": "NOT_DISPATCHED", "reason": "CHROMIUM_MISSING"}
            if not os.access(executable, os.X_OK):
                return {"status": "FAILED", "reason": "CHROMIUM_NOT_EXECUTABLE"}
            return {"status": "READY", "browser_executable": executable}
    except Exception as exc:
        return {
            "status": "FAILED",
            "reason": "PLAYWRIGHT_START_FAILED",
            "detail": str(exc),
        }


def _read_result(report: Path, returncode: int) -> dict:
    try:
        root = ET.parse(report).getroot()
        cases = root.findall(".//testcase")
        counts = {
            "collected": len(cases),
            "failed": sum(case.find("failure") is not None for case in cases),
            "errors": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases),
        }
    except (OSError, ET.ParseError) as exc:
        return {
            "status": "FAILED",
            "reason": "TEST_REPORT_MISSING_OR_INVALID",
            "detail": str(exc),
        }
    counts["passed"] = (
        counts["collected"] - counts["failed"] - counts["errors"] - counts["skipped"]
    )
    if returncode or counts["failed"] or counts["errors"]:
        status, reason = "FAILED", "PYTEST_FAILED"
    elif counts["collected"] != EXPECTED_CASES or counts["skipped"]:
        status, reason = "FAILED", "INCOMPLETE_BROWSER_CHECK"
    else:
        status, reason = "PASSED", "ALL_APPROVED_BROWSER_CASES_PASSED"
    return {
        "status": status,
        "reason": reason,
        "counts": counts,
        "cases": [case.get("name") for case in cases],
    }


def run() -> dict:
    receipt = {
        "test_file": TEST_PATH,
        "expected_cases": EXPECTED_CASES,
        "python": sys.version.split()[0],
        "dispatched": False,
    }
    preflight = _preflight()
    receipt["preflight"] = preflight
    if preflight["status"] != "READY":
        return {**receipt, "status": preflight["status"], "reason": preflight["reason"]}
    with tempfile.TemporaryDirectory(prefix="ccz119-browser-") as directory:
        report = Path(directory) / "junit.xml"
        argv = [sys.executable, "-m", "pytest", "-q", TEST_PATH, f"--junitxml={report}"]
        receipt["argv"] = argv
        try:
            process = subprocess.run(
                argv,
                cwd=ROOT,
                env=_environment(),
                text=True,
                capture_output=True,
                timeout=TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                **receipt,
                "dispatched": True,
                "status": "FAILED",
                "reason": "PYTEST_TIMEOUT",
            }
        except OSError as exc:
            return {
                **receipt,
                "status": "FAILED",
                "reason": "PYTEST_START_FAILED",
                "detail": str(exc),
            }
        receipt.update(
            dispatched=True,
            returncode=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
        )
        return {**receipt, **_read_result(report, process.returncode)}


def main() -> int:
    receipt = run()
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return {"PASSED": 0, "NOT_DISPATCHED": 2}.get(receipt["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
