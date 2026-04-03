"""CLI entrypoint for legal-chunking."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from legal_chunking.api import chunk_pdf, chunk_text
from legal_chunking.models import Document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legal-chunking")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("chunk", "structure", "explain"):
        command_parser = subparsers.add_parser(command)
        input_group = command_parser.add_mutually_exclusive_group(required=True)
        input_group.add_argument("--text", help="Raw text input.")
        input_group.add_argument("--path", help="Path to a text or PDF file.")
        command_parser.add_argument("--profile", default="generic", help="Chunking profile.")
        command_parser.add_argument("--doc-kind", default=None, help="Optional document kind.")
    return parser


def _load_document(
    *,
    text: str | None,
    path: str | None,
    profile: str,
    doc_kind: str | None,
    trace: bool,
) -> Document:
    if text is not None:
        return chunk_text(text, profile=profile, doc_kind=doc_kind, trace=trace)

    if path is None:
        raise ValueError("Either --text or --path must be provided.")

    source = Path(path)
    if source.suffix.lower() == ".pdf":
        return chunk_pdf(source, profile=profile, doc_kind=doc_kind, trace=trace)
    return chunk_text(
        source.read_text(encoding="utf-8"),
        profile=profile,
        source_name=source.name,
        doc_kind=doc_kind,
        trace=trace,
    )


def _serialize_payload(command: str, document: Document) -> dict[str, object]:
    if command == "chunk":
        return {
            "source_name": document.source_name,
            "profile": document.profile,
            "language": document.language,
            "chunk_policy": document.chunk_policy,
            "chunks": [asdict(chunk) for chunk in document.chunks],
        }
    if command == "structure":
        return {
            "source_name": document.source_name,
            "profile": document.profile,
            "language": document.language,
            "chunk_policy": document.chunk_policy,
            "sections": [asdict(section) for section in document.sections],
        }
    if command == "explain":
        trace = document.trace
        return {
            "source_name": document.source_name,
            "profile": document.profile,
            "language": document.language,
            "chunk_policy": document.chunk_policy,
            "trace": asdict(trace) if trace is not None else {"events": []},
        }
    raise ValueError(f"Unsupported command: {command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    document = _load_document(
        text=args.text,
        path=args.path,
        profile=args.profile,
        doc_kind=args.doc_kind,
        trace=args.command == "explain",
    )
    print(
        json.dumps(
            _serialize_payload(args.command, document),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
