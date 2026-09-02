#!/usr/bin/env python3
"""Cross-language parity check: Python CLI vs Rust binary.

Runs both implementations against the SAME shared mock server (correct
contract, then broken contract) and asserts their JSON reports are identical.
This locks the "provably behaviorally equivalent" claim into CI: any drift in
config parsing, checks, or reporting between schemalock/ and rust/ fails here.

Usage:
    python3 scripts/parity_check.py --rust-binary rust/target/debug/schemalock
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = REPO_ROOT / "examples" / "escrow_api.yaml"

BASE_URL = "http://127.0.0.1"


def _wait_for_server(port: int, timeout: float = 20.0) -> None:
    url = f"{BASE_URL}:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError(f"mock server on port {port} did not become healthy")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run(cmd, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)


def _run_python_cli(
    port: int, report_path: Path, extra_args: list[str]
) -> subprocess.CompletedProcess:
    return _run(
        [
            sys.executable,
            "-m",
            "schemalock.cli",
            "test",
            "--config",
            str(CONFIG),
            "--base-url",
            f"{BASE_URL}:{port}",
            "--json-report",
            str(report_path),
            *extra_args,
        ],
        cwd=REPO_ROOT,
    )


def _run_rust_cli(
    binary: Path, port: int, report_path: Path, extra_args: list[str]
) -> subprocess.CompletedProcess:
    return _run(
        [
            str(binary),
            "test",
            "--config",
            str(CONFIG),
            "--base-url",
            f"{BASE_URL}:{port}",
            "--json-report",
            str(report_path),
            *extra_args,
        ],
        cwd=REPO_ROOT,
    )


def _compare(
    label: str,
    py_report: Path,
    rust_report: Path,
    py_proc: subprocess.CompletedProcess,
    rust_proc: subprocess.CompletedProcess,
) -> bool:
    errors = []

    if py_proc.returncode != rust_proc.returncode:
        errors.append(
            f"exit codes differ: python={py_proc.returncode}, rust={rust_proc.returncode}"
        )

    py_json = json.loads(py_report.read_text())
    rust_json = json.loads(rust_report.read_text())

    if py_json != rust_json:
        errors.append("JSON reports are not identical")
        a = json.dumps(py_json, indent=2, sort_keys=True).splitlines()
        b = json.dumps(rust_json, indent=2, sort_keys=True).splitlines()
        errors.append("\n".join(difflib.unified_diff(a, b, "python", "rust", lineterm="")))

    if errors:
        print(f"[FAIL] parity mismatch ({label}):", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        return False

    print(f"[ok] parity matches ({label})")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rust-binary", required=True)
    args = parser.parse_args()

    binary = Path(args.rust_binary)
    if not binary.is_file():
        print(f"rust binary not found: {binary}", file=sys.stderr)
        return 2

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for label, env_extra, extra_args in (
            ("correct contract", None, []),
            ("broken contract", {"MOCK_BREAK_CONTRACT": "1"}, []),
            # --max-response-bytes parity (issue #14): a cap smaller than any
            # mock body must produce identical oversized-response errors, and
            # a generous cap must match the uncapped baseline exactly.
            ("bounded oversized", None, ["--max-response-bytes", "10"]),
            ("bounded within cap", None, ["--max-response-bytes", "10485760"]),
        ):
            port = _free_port()
            server_env = dict(os.environ)
            if env_extra:
                server_env.update(env_extra)

            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "examples.mock_server:app",
                    "--port",
                    str(port),
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=server_env,
            )
            try:
                _wait_for_server(port)
                slug = label.replace(" ", "_").replace(":", "_")
                py_report = Path(tmp) / f"python_{slug}.json"
                rust_report = Path(tmp) / f"rust_{slug}.json"
                py_proc = _run_python_cli(port, py_report, extra_args)
                rust_proc = _run_rust_cli(binary, port, rust_report, extra_args)
                ok = _compare(label, py_report, rust_report, py_proc, rust_proc) and ok
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
