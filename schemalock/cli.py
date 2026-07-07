"""schemalock CLI — `schemalock test --config schemalock.yaml --base-url ...`"""

from __future__ import annotations

import argparse
import sys

from schemalock.config import ConfigError, load_config
from schemalock.report import exit_code, render_console, render_json
from schemalock.runner import Runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="schemalock")
    sub = parser.add_subparsers(dest="command", required=True)

    test_cmd = sub.add_parser("test", help="Run contract checks against a target")
    test_cmd.add_argument("--config", required=True, help="Path to schemalock.yaml")
    test_cmd.add_argument(
        "--base-url", default=None, help="Target base URL (overrides config.base_url)"
    )
    test_cmd.add_argument(
        "--auth-header",
        default=None,
        help="Default auth header for authenticated requests, e.g. 'Authorization: Bearer xyz'",
    )
    test_cmd.add_argument("--json-report", default=None, help="Write JSON report to this path")
    test_cmd.add_argument(
        "--timeout", type=float, default=10.0, help="Per-request timeout in seconds"
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
                auth_header=args.auth_header,
                timeout=args.timeout,
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

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
