"""CLI entrypoint for legal-chunking."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

from legal_chunking.api import chunk_pages, chunk_pdf, chunk_text
from legal_chunking.extract.models import ExtractedPage
from legal_chunking.extract.pdf import extract_pdf_text
from legal_chunking.models import Document
from legal_chunking.reference_parser import analyze_references


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legal-chunking")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("chunk", "structure", "explain", "review", "references"):
        command_parser = subparsers.add_parser(command)
        input_group = command_parser.add_mutually_exclusive_group(required=True)
        input_group.add_argument("--text", help="Raw text input.")
        input_group.add_argument("--path", help="Path to a text or PDF file.")
        if command != "references":
            input_group.add_argument(
                "--pages-json",
                help="Path to a JSON file containing [{'page_number': int, 'text': str}, ...].",
            )
        command_parser.add_argument("--profile", default="generic", help="Chunking profile.")
        if command == "references":
            command_parser.add_argument(
                "--doc-family",
                default=None,
                help="Optional manifest document family filter.",
            )
        else:
            command_parser.add_argument("--doc-kind", default=None, help="Optional document kind.")
        command_parser.add_argument(
            "--output",
            default=None,
            help="Optional output file path for JSON or review text.",
        )
        command_parser.add_argument(
            "--backend", choices=("pymupdf", "pymupdf4llm"), default="pymupdf"
        )
        command_parser.add_argument("--ocr", choices=("off", "auto", "force"), default="off")
        command_parser.add_argument("--ocr-language", default="eng")
        command_parser.add_argument("--ocr-dpi", type=int, default=300)
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


def _load_pages_json(source: Path) -> list[ExtractedPage]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Pages JSON must be a list of {'page_number', 'text'} objects.")
    pages: list[ExtractedPage] = []
    for item in payload:
        if not isinstance(item, dict) or "page_number" not in item or "text" not in item:
            raise ValueError("Each page entry must be an object with 'page_number' and 'text'.")
        if not isinstance(item["text"], str):
            raise ValueError("Each page entry 'text' must be a string.")
        pages.append(ExtractedPage(page_number=item["page_number"], text=item["text"]))
    return pages


def _load_document(
    *,
    text: str | None,
    path: str | None,
    pages_json: str | None = None,
    profile: str,
    doc_kind: str | None,
    trace: bool,
    backend: str = "pymupdf",
    ocr: str = "off",
    ocr_language: str = "eng",
    ocr_dpi: int = 300,
) -> Document:
    if text is not None:
        if backend != "pymupdf" or ocr != "off":
            raise ValueError("Extraction options require a PDF path")
        return chunk_text(text, profile=profile, doc_kind=doc_kind, trace=trace)

    if pages_json is not None:
        if backend != "pymupdf" or ocr != "off":
            raise ValueError("Extraction options require a PDF path")
        source = Path(pages_json)
        return chunk_pages(
            _load_pages_json(source),
            profile=profile,
            source_name=source.name,
            doc_kind=doc_kind,
            trace=trace,
        )

    if path is None:
        raise ValueError("One of --text, --path, or --pages-json must be provided.")

    source = Path(path)
    if source.suffix.lower() == ".pdf":
        return chunk_pdf(
            source,
            profile=profile,
            doc_kind=doc_kind,
            trace=trace,
            backend=backend,
            ocr=ocr,
            ocr_language=ocr_language,
            ocr_dpi=ocr_dpi,
        )
    if backend != "pymupdf" or ocr != "off":
        raise ValueError("Extraction options require a PDF path")
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
        page_suffix = f" | page={chunk.page}" if chunk.page is not None else ""
        lines.extend(
            [
                (
                    f"[{chunk.order}] {chunk.section_title or '-'}"
                    f" | method={chunk.chunk_method}"
                    f"{page_suffix}"
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


def _load_reference_text(
    *,
    text: str | None,
    path: str | None,
    profile: str,
    backend: str = "pymupdf",
    ocr: str = "off",
    ocr_language: str = "eng",
    ocr_dpi: int = 300,
) -> str:
    if text is not None:
        if backend != "pymupdf" or ocr != "off":
            raise ValueError("Extraction options require a PDF path")
        return text
    if path is None:
        raise ValueError("Either --text or --path must be provided.")
    source = Path(path)
    if source.suffix.lower() == ".pdf":
        return extract_pdf_text(
            source,
            profile=profile,
            backend=backend,
            ocr=ocr,
            ocr_language=ocr_language,
            ocr_dpi=ocr_dpi,
        )
    if backend != "pymupdf" or ocr != "off":
        raise ValueError("Extraction options require a PDF path")
    return source.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "references":
        raw_text = _load_reference_text(
            text=args.text,
            path=args.path,
            profile=args.profile,
            backend=args.backend,
            ocr=args.ocr,
            ocr_language=args.ocr_language,
            ocr_dpi=args.ocr_dpi,
        )
        analysis = analyze_references(raw_text, profile=args.profile, doc_family=args.doc_family)
        _emit_output(
            json.dumps(asdict(analysis), ensure_ascii=False, indent=2),
            output=args.output,
        )
        return 0
    document = _load_document(
        text=args.text,
        path=args.path,
        pages_json=args.pages_json,
        profile=args.profile,
        doc_kind=args.doc_kind,
        trace=args.command == "explain",
        backend=args.backend,
        ocr=args.ocr,
        ocr_language=args.ocr_language,
        ocr_dpi=args.ocr_dpi,
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
