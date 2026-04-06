"""CLI entrypoint for legal-chunking."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

from legal_chunking.api import chunk_pdf, chunk_text
from legal_chunking.models import Document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legal-chunking")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("chunk", "structure", "explain", "review"):
        command_parser = subparsers.add_parser(command)
        input_group = command_parser.add_mutually_exclusive_group(required=True)
        input_group.add_argument("--text", help="Raw text input.")
        input_group.add_argument("--path", help="Path to a text or PDF file.")
        command_parser.add_argument("--profile", default="generic", help="Chunking profile.")
        command_parser.add_argument("--doc-kind", default=None, help="Optional document kind.")
        command_parser.add_argument(
            "--output",
            default=None,
            help="Optional output file path for JSON or review text.",
        )
        if command == "review":
            command_parser.add_argument(
                "--limit",
                type=int,
                default=20,
                help="Maximum number of sections and chunks to render.",
            )
            command_parser.add_argument(
                "--max-chars",
                type=int,
                default=240,
                help="Maximum preview length per section or chunk.",
            )
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


def _preview(text: str, *, max_chars: int) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= max_chars:
        return collapsed
    return f"{collapsed[: max_chars - 1].rstrip()}…"


def _render_review(document: Document, *, limit: int, max_chars: int) -> str:
    lines = [
        f"Source: {document.source_name}",
        f"Profile: {document.profile}",
        f"Language: {document.language or 'unknown'}",
        f"Chunk policy: {document.chunk_policy}",
        f"Sections: {len(document.sections)}",
        f"Chunks: {len(document.chunks)}",
        "",
        "Sections",
    ]
    for section in document.sections[:limit]:
        lines.extend(
            [
                (
                    f"[{section.order}] {section.title} | kind={section.kind}"
                    f" | type={section.section_type or '-'}"
                ),
                f"  preview: {_preview(section.text, max_chars=max_chars)}",
            ]
        )
    if len(document.sections) > limit:
        lines.append(f"  ... {len(document.sections) - limit} more sections")

    lines.extend(["", "Chunks"])
    for chunk in document.chunks[:limit]:
        lines.extend(
            [
                (
                    f"[{chunk.order}] {chunk.section_title or '-'}"
                    f" | method={chunk.chunk_method}"
                    f" | chunk_id={chunk.chunk_id}"
                ),
                f"  preview: {_preview(chunk.text, max_chars=max_chars)}",
            ]
        )
    if len(document.chunks) > limit:
        lines.append(f"  ... {len(document.chunks) - limit} more chunks")

    return "\n".join(lines)


def _emit_output(content: str, *, output: str | None) -> None:
    if output is None:
        print(content)
        return
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content + "\n", encoding="utf-8")


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
    if args.command == "review":
        _emit_output(
            _render_review(
                document,
                limit=args.limit,
                max_chars=args.max_chars,
            ),
            output=args.output,
        )
        return 0
    _emit_output(
        json.dumps(_serialize_payload(args.command, document), ensure_ascii=False, indent=2),
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
