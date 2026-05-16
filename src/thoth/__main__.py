"""CLI entrypoint for Thoth."""

from __future__ import annotations

import argparse

from thoth.app import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thoth", description="Thoth runtime CLI")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument(
        "--message",
        default="hello from thoth",
        help="Message payload sent through the runtime envelope",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Optional explicit session id for the request",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        from thoth import __version__

        print(__version__)
        return 0

    return run(message=args.message, session_id=args.session_id)


if __name__ == "__main__":
    raise SystemExit(main())
