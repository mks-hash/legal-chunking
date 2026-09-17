"""Private subprocess protocol for the optional layout/OCR adapter."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict

from legal_chunking.errors import PdfDependencyError
from legal_chunking.tracing import TraceCollector

from .pymupdf4llm import _extract_layout_pages_in_process


def main() -> None:
    path, ocr, language, dpi, tracing = sys.argv[1:]
    collector = TraceCollector() if tracing == "True" else None
    try:
        # Redirect only in this dedicated process; host threads are unaffected.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            pages = _extract_layout_pages_in_process(
                path, ocr=ocr, language=language, dpi=int(dpi), trace=collector
            )
        payload = {
            "pages": [asdict(p) for p in pages],
            "events": [asdict(e) for e in collector.to_report().events] if collector else [],
        }
    except PdfDependencyError as exc:
        payload = {"error": {"kind": "dependency", "message": str(exc)}}
    except Exception as exc:
        # Upstream exception text may contain document contents or native paths.
        payload = {
            "error": {
                "kind": "extraction",
                "message": f"PyMuPDF4LLM extraction failed ({type(exc).__name__})",
            }
        }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
