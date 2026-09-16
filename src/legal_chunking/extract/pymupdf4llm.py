"""Optional layout extraction with an explicit Tesseract OCR callback."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from legal_chunking.errors import ExtractionError, PdfDependencyError
from legal_chunking.tracing import TraceCollector, TraceStage

from .models import ExtractedPage

if TYPE_CHECKING:
    import pymupdf


def extract_layout_pages(
    path: str | Path, *, ocr: str, language: str, dpi: int, trace: TraceCollector | None
) -> list[ExtractedPage]:
    # Upstream activates global layout state, uses a global diagnostic buffer
    # and emits parser messages. Isolate these effects from the host and the
    # text/native-PDF engine; no process-global stdout or cwd changes here.
    worker_env = os.environ.copy()
    if worker_env.get("TESSDATA_PREFIX"):
        worker_env["TESSDATA_PREFIX"] = str(Path(worker_env["TESSDATA_PREFIX"]).resolve())
    with TemporaryDirectory(prefix="legal-chunking-layout-") as workdir:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "legal_chunking.extract.pymupdf4llm_worker",
                str(Path(path).resolve()),
                ocr,
                language,
                str(dpi),
                str(trace is not None),
            ],
            capture_output=True,
            text=True,
            cwd=workdir,
            env=worker_env,
            check=False,
        )
    if result.returncode != 0:
        raise ExtractionError("PyMuPDF4LLM worker failed; check the optional installation")
    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        raise ExtractionError("Invalid PyMuPDF4LLM worker response") from exc
    if "error" in payload:
        error = payload["error"]
        if error["kind"] == "dependency":
            raise PdfDependencyError(error["message"])
        raise ExtractionError(error["message"])
    if trace is not None:
        for event in payload["events"]:
            trace.emit(TraceStage(event["stage"]), event["type"], **event["data"])
    return [ExtractedPage(**item) for item in payload["pages"]]


def _extract_layout_pages_in_process(
    path: str | Path,
    *,
    ocr: str,
    language: str,
    dpi: int,
    trace: TraceCollector | None,
) -> list[ExtractedPage]:
    try:
        import pymupdf
        import pymupdf4llm
    except ImportError as exc:
        raise PdfDependencyError(
            "PyMuPDF4LLM is required. Install with: pip install 'legal-chunking[ocr]'"
        ) from exc

    tessdata = None
    if ocr != "off":
        try:
            tessdata = pymupdf.get_tessdata()
        except RuntimeError as exc:
            raise PdfDependencyError(
                "OCR requires Tesseract traineddata. Set TESSDATA_PREFIX to its directory."
            ) from exc
        if not tessdata or any(
            not (Path(tessdata) / f"{name}.traineddata").is_file() for name in language.split("+")
        ):
            raise PdfDependencyError(f"Missing Tesseract traineddata for {language!r}")

    if trace is not None and tessdata is not None:
        trace.emit(
            TraceStage.EXTRACT,
            "ocr_configuration",
            engine="tesseract",
            language=language,
            dpi=dpi,
            model_hashes={
                name: hashlib.sha256(
                    (Path(tessdata) / f"{name}.traineddata").read_bytes()
                ).hexdigest()
                for name in language.split("+")
            },
        )
    requested_dpi = dpi

    def run_ocr(
        page: pymupdf.Page,
        dpi: int = dpi,
        pixmap: pymupdf.Pixmap | None = None,
        language: str = language,
        keep_ocr_text: bool = False,
    ) -> None:
        # The callback writes a text-only OCR overlay into the in-memory document.
        # It never saves or changes the source PDF on disk.
        # PyMuPDF4LLM 1.28.2's to_text wrapper does not forward ocr_dpi to its
        # layout parser. Honor our explicit setting inside the callback.
        pix = page.get_pixmap(dpi=requested_dpi, alpha=False)
        data = pix.pdfocr_tobytes(language=language, tessdata=tessdata)
        with pymupdf.open("pdf", data) as recognized:
            overlay = recognized[0]
            if not overlay.get_text("text").strip():
                if trace is not None:
                    trace.emit(
                        TraceStage.EXTRACT,
                        "ocr_page_processed",
                        page_number=page.number + 1,
                        engine="tesseract",
                        language=language,
                        dpi=requested_dpi,
                        text_detected=False,
                    )
                return
            overlay.add_redact_annot(overlay.rect)
            overlay.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_REMOVE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                text=pymupdf.PDF_REDACT_TEXT_NONE,
            )
            page.add_redact_annot(page.rect)
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_NONE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                text=pymupdf.PDF_REDACT_TEXT_REMOVE,
            )
            page.show_pdf_page(page.rect, recognized, 0)
        if trace is not None:
            trace.emit(
                TraceStage.EXTRACT,
                "ocr_page_processed",
                page_number=page.number + 1,
                engine="tesseract",
                language=language,
                dpi=requested_dpi,
            )

    # to_text avoids feeding Markdown presentation syntax to legal detectors.
    # No global use_layout toggles: backend calls remain re-entrant.
    with pymupdf.open(Path(path)) as document:
        output = pymupdf4llm.to_text(
            document,
            page_chunks=True,
            use_ocr=ocr != "off",
            force_ocr=ocr == "force",
            ocr_function=run_ocr if ocr != "off" else None,
            ocr_language=language,
            ocr_dpi=dpi,
            header=True,
            footer=True,
            show_progress=False,
        )
    if not isinstance(output, list):
        raise ValueError("PyMuPDF4LLM must return page chunks")
    pages: list[ExtractedPage] = []
    for item in output:
        number = item["metadata"]["page_number"]
        text = item["text"]
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise ValueError("Invalid PyMuPDF4LLM page number")
        if not isinstance(text, str):
            raise ValueError("Invalid PyMuPDF4LLM page text")
        pages.append(ExtractedPage(page_number=number, text=text))
    return pages
