import os
import socket
import subprocess
import sys
import time

import pytest
from schemalock.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.1)
    raise RuntimeError(f"mock server did not start listening on port {port} in time")


@pytest.fixture()
def mock_server():
    port = _free_port()
    env = dict(os.environ)
    env["MOCK_BREAK_CONTRACT"] = "0"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "examples.mock_server:app", "--port", str(port)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_for_port(port)
        yield port
    finally:
        proc.terminate()
        proc.wait(timeout=5)


@pytest.fixture()
def broken_mock_server():
    port = _free_port()
    env = dict(os.environ)
    env["MOCK_BREAK_CONTRACT"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "examples.mock_server:app", "--port", str(port)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_for_port(port)
        yield port
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_cli_version_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "schemalock 0.2.0" in capsys.readouterr().out


def test_cli_passes_against_correct_mock_server(mock_server, tmp_path, capsys):
    report_path = str(tmp_path / "report.json")
    exit_code = main(
        [
            "test",
            "--config",
            os.path.join(REPO_ROOT, "examples", "escrow_api.yaml"),
            "--base-url",
            f"http://127.0.0.1:{mock_server}",
            "--json-report",
            report_path,
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0, out
    assert os.path.exists(report_path)


def test_cli_fails_against_broken_mock_server(broken_mock_server, capsys):
    exit_code = main(
        [
            "test",
            "--config",
            os.path.join(REPO_ROOT, "examples", "escrow_api.yaml"),
            "--base-url",
            f"http://127.0.0.1:{broken_mock_server}",
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "FAILED" in out


def _config_without_auth(tmp_path) -> str:
    import yaml

    with open(os.path.join(REPO_ROOT, "examples", "escrow_api.yaml"), encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    raw.pop("auth_header", None)
    path = tmp_path / "no_auth.yaml"
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(raw, fh)
    return str(path)


def test_auth_header_read_from_env(mock_server, tmp_path, capsys, monkeypatch):
    config = _config_without_auth(tmp_path)
    base = f"http://127.0.0.1:{mock_server}"

    monkeypatch.setenv("SCHEMALOCK_AUTH_HEADER", "Authorization: Bearer wrong-token")
    exit_code = main(["test", "--config", config, "--base-url", base])
    assert exit_code == 1, "wrong token from env should fail the contract"

    monkeypatch.setenv("SCHEMALOCK_AUTH_HEADER", "Authorization: Bearer valid-token")
    exit_code = main(["test", "--config", config, "--base-url", base])
    assert exit_code == 0, "valid token from env should pass the contract"


def test_cli_flag_overrides_env(mock_server, tmp_path, capsys, monkeypatch):
    config = _config_without_auth(tmp_path)
    base = f"http://127.0.0.1:{mock_server}"

    monkeypatch.setenv("SCHEMALOCK_AUTH_HEADER", "Authorization: Bearer wrong-token")
    exit_code = main(
        [
            "test",
            "--config",
            config,
            "--base-url",
            base,
            "--auth-header",
            "Authorization: Bearer valid-token",
        ]
    )
    assert exit_code == 0, "--auth-header flag should take precedence over env"
