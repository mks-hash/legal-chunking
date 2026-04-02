"""CLI entrypoint for legal-chunking."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from legal_chunking.api import chunk_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legal-chunking")
    parser.add_argument("--text", required=True, help="Raw text to chunk.")
    parser.add_argument("--profile", default="generic", help="Chunking profile.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    document = chunk_text(args.text, profile=args.profile)
    print(json.dumps(asdict(document), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
