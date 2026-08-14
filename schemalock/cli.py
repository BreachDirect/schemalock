"""schemalock CLI — `schemalock test --config schemalock.yaml --base-url ...`"""

from __future__ import annotations

import argparse
import os
import sys

from schemalock import __version__
from schemalock.config import ConfigError, load_config
from schemalock.report import exit_code, render_console, render_json
from schemalock.runner import Runner
from schemalock.scaffold import CaptureError, scaffold


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="schemalock")
    parser.add_argument(
        "--version",
        action="version",
        version=f"schemalock {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    test_cmd = sub.add_parser("test", help="Run contract checks against a target")
    test_cmd.add_argument("--config", required=True, help="Path to schemalock.yaml")
    test_cmd.add_argument(
        "--base-url", default=None, help="Target base URL (overrides config.base_url)"
    )
    test_cmd.add_argument(
        "--auth-header",
        default=None,
        help="Default auth header for authenticated requests, e.g. 'Authorization: Bearer xyz'. "
        "Falls back to the SCHEMALOCK_AUTH_HEADER env var (safer than argv, which is visible "
        "in process listings and shell history).",
    )
    test_cmd.add_argument("--json-report", default=None, help="Write JSON report to this path")
    test_cmd.add_argument(
        "--timeout", type=float, default=10.0, help="Per-request timeout in seconds"
    )
    test_cmd.add_argument(
        "--max-response-bytes",
        type=int,
        default=None,
        help="Abort a request whose response body exceeds this many bytes (default: 10 MiB)",
    )

    scaffold_cmd = sub.add_parser(
        "scaffold",
        help="Generate schemalock.yaml from a SchemaLock Recorder capture.json",
    )
    scaffold_cmd.add_argument("capture", help="Path to capture.json from the recorder extension")
    scaffold_cmd.add_argument(
        "--name",
        default=None,
        help="Contract name (default: 'Recorded API contract')",
    )
    scaffold_cmd.add_argument("--base-url", default=None, help="Override the inferred base URL")
    scaffold_cmd.add_argument(
        "--output", default=None, help="Write YAML to this path (default: print to stdout)"
    )

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "test":
        try:
            config = load_config(args.config)
        except ConfigError as e:
            print(f"SchemaLock config error: {e}", file=sys.stderr)
            return 2

        try:
            runner = Runner(
                config,
                base_url=args.base_url,
                auth_header=args.auth_header or os.environ.get("SCHEMALOCK_AUTH_HEADER"),
                timeout=args.timeout,
                max_response_bytes=args.max_response_bytes,
            )
        except ValueError as e:
            print(f"SchemaLock error: {e}", file=sys.stderr)
            return 2

        results = runner.run()
        print(render_console(config.name, results))

        if args.json_report:
            render_json(config.name, results, args.json_report)
            print(f"\nJSON report written to {args.json_report}")

        return exit_code(results)

    if args.command == "scaffold":
        try:
            yaml_text, notes = scaffold(args.capture, name=args.name, base_url=args.base_url)
        except CaptureError as e:
            print(f"SchemaLock capture error: {e}", file=sys.stderr)
            return 2

        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(yaml_text)
            print(f"Contract written to {args.output}")
        else:
            print(yaml_text, end="")

        for note in notes:
            print(f"Note: {note}", file=sys.stderr)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
