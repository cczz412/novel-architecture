"""The browser receipt must not turn missing, skipped or failed runs into PASS."""

from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from tools import ccz119_browser_test as runner


def write_report(path, *, passed=8, skipped=0, failed=0, errors=0):
    cases = ['<testcase name="passed" />'] * passed
    cases += ['<testcase name="skipped"><skipped /></testcase>'] * skipped
    cases += ['<testcase name="failed"><failure /></testcase>'] * failed
    cases += ['<testcase name="error"><error /></testcase>'] * errors
    path.write_text(
        "<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>"
    )


@pytest.mark.parametrize("reason", ["PLAYWRIGHT_MISSING", "CHROMIUM_MISSING"])
def test_missing_environment_never_dispatches(monkeypatch, reason):
    monkeypatch.setattr(
        runner, "_preflight", lambda: {"status": "NOT_DISPATCHED", "reason": reason}
    )
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *a, **k: pytest.fail("must not dispatch")
    )
    receipt = runner.run()
    assert receipt["status"] == "NOT_DISPATCHED"
    assert receipt["reason"] == reason
    assert receipt["dispatched"] is False


@pytest.mark.parametrize(
    "passed,skipped,failed,errors,code",
    [
        (0, 0, 0, 0, 0),
        (0, 8, 0, 0, 0),
        (7, 1, 0, 0, 0),
        (7, 0, 0, 0, 0),
        (7, 0, 1, 0, 1),
        (7, 0, 0, 1, 0),
        (8, 0, 0, 0, 1),
    ],
)
def test_incomplete_or_failed_result_is_not_pass(
    tmp_path, passed, skipped, failed, errors, code
):
    report = tmp_path / "junit.xml"
    write_report(report, passed=passed, skipped=skipped, failed=failed, errors=errors)
    assert runner._read_result(report, code)["status"] == "FAILED"


@pytest.mark.parametrize("content", [None, "<broken>"])
def test_missing_or_invalid_report_fails(tmp_path, content):
    report = tmp_path / "junit.xml"
    if content is not None:
        report.write_text(content)
    assert runner._read_result(report, 0)["reason"] == "TEST_REPORT_MISSING_OR_INVALID"


def test_exact_target_and_isolated_environment(monkeypatch):
    monkeypatch.setattr(runner, "_preflight", lambda: {"status": "READY"})
    monkeypatch.setenv("OPENAI_API_KEY", "fake-must-not-pass")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k memory_render")
    monkeypatch.setenv("PYTHONPATH", "/fake/injection")

    def execute(argv, **kwargs):
        assert argv[:5] == [
            runner.sys.executable,
            "-m",
            "pytest",
            "-q",
            runner.TEST_PATH,
        ]
        assert kwargs["cwd"] == runner.ROOT
        assert kwargs["timeout"] == runner.TIMEOUT_SECONDS
        assert (
            not {"OPENAI_API_KEY", "PYTEST_ADDOPTS", "PYTHONPATH"}
            & kwargs["env"].keys()
        )
        assert kwargs["env"]["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] == "1"
        assert kwargs["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
        write_report(Path(argv[-1].split("=", 1)[1]))
        return SimpleNamespace(returncode=0, stdout="8 passed", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", execute)
    receipt = runner.run()
    assert receipt["status"] == "PASSED"
    assert receipt["counts"] == {
        "collected": 8,
        "passed": 8,
        "skipped": 0,
        "failed": 0,
        "errors": 0,
    }
    assert receipt["dispatched"] is True


@pytest.mark.parametrize(
    "error,reason,dispatched",
    [
        (OSError("cannot spawn"), "PYTEST_START_FAILED", False),
        (subprocess.TimeoutExpired("pytest", 180), "PYTEST_TIMEOUT", True),
    ],
)
def test_process_failure_is_not_pass(monkeypatch, error, reason, dispatched):
    monkeypatch.setattr(runner, "_preflight", lambda: {"status": "READY"})

    def execute(*args, **kwargs):
        raise error

    monkeypatch.setattr(runner.subprocess, "run", execute)
    receipt = runner.run()
    assert receipt["status"] == "FAILED"
    assert receipt["reason"] == reason
    assert receipt["dispatched"] is dispatched


@pytest.mark.parametrize(
    "status,exit_code", [("PASSED", 0), ("NOT_DISPATCHED", 2), ("FAILED", 1)]
)
def test_cli_exit_code_matches_receipt(monkeypatch, capsys, status, exit_code):
    monkeypatch.setattr(runner, "run", lambda: {"status": status})
    assert runner.main() == exit_code
    assert status in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["missing", "not_executable", "driver_start", "driver_probe", "ready"])
def test_real_preflight_checks_browser_prerequisites(monkeypatch, tmp_path, failure):
    import sys
    from types import ModuleType

    executable = tmp_path / "chromium"
    if failure in {"not_executable", "ready"}:
        executable.write_text("browser placeholder")
        executable.chmod(0o700 if failure == "ready" else 0o600)
    events = []

    def new_context():
        events.append("probe")
        if failure == "driver_probe":
            raise OSError("driver handshake failed")
        return SimpleNamespace(dispose=lambda: events.append("dispose"))

    class Driver:
        def __enter__(self):
            if failure == "driver_start":
                raise OSError("driver cannot start")
            return SimpleNamespace(
                chromium=SimpleNamespace(executable_path=str(executable)),
                request=SimpleNamespace(new_context=new_context),
            )

        def __exit__(self, *args):
            return False

    package = ModuleType("playwright")
    sync_api = ModuleType("playwright.sync_api")
    sync_api.sync_playwright = Driver
    monkeypatch.setitem(sys.modules, "playwright", package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    monkeypatch.setattr(runner.shutil, "which", lambda name: None)
    receipt = runner._preflight()
    if failure != "driver_start":
        assert events == (["probe"] if failure == "driver_probe" else ["probe", "dispose"])
    if failure == "ready":
        assert receipt == {"status": "READY", "browser_executable": str(executable)}
        return
    assert (
        receipt["reason"]
        == {
            "missing": "CHROMIUM_MISSING",
            "not_executable": "CHROMIUM_NOT_EXECUTABLE",
            "driver_start": "PLAYWRIGHT_START_FAILED",
            "driver_probe": "PLAYWRIGHT_START_FAILED",
        }[failure]
    )
    assert receipt["status"] == ("NOT_DISPATCHED" if failure == "missing" else "FAILED")
