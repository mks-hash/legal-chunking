# Optional PDF and OCR extraction

The text core accepts text from any extractor through `chunk_text`. Extraction
backend choice does not redefine profiles, legal structure, hashing or chunk policy.
Docling is not implemented or required by this package.

## Backends

| Backend | Extra | Behavior |
| --- | --- | --- |
| `pymupdf` (default) | `pdf` | Native text and line order; no OCR |
| `pymupdf4llm` | `ocr` | Layout-aware plain-text projection; optional explicit OCR |

```bash
pip install 'legal-chunking[ocr]'
```

```python
from legal_chunking import chunk_pdf

document = chunk_pdf(
    "scan.pdf", profile="ru", doc_kind="court_guidance",
    backend="pymupdf4llm", ocr="auto", ocr_language="rus+eng", ocr_dpi=300,
    trace=True,
)
```

OCR modes: `off` disables recognition; `auto` lets the selected layout extractor
identify pages needing recognition; `force` requests recognition even on native
pages. Using auto/force with the default native backend is an explicit error.
Languages name installed traineddata files, separated by `+`; DPI is an integer
from 72 to 600. The default language is `eng`, not inferred from jurisdiction.

Install Tesseract language data separately and set `TESSDATA_PREFIX` to the directory
containing e.g. `rus.traineddata` and `eng.traineddata`. The package neither downloads
models nor installs system tools. The OCR callback uses PyMuPDF's Tesseract binding;
missing data is an actionable dependency error, not a fallback to another OCR engine.
The default dev extra includes the layout library, but not traineddata.

## Repeated margin cleanup

Repeated line text is not globally removed from all page positions. Repetition
can identify contiguous leading or trailing margin fragments; cleanup stops at
an explicit legal heading, enumeration or completed sentence. Leading cleanup also
protects numeric heading candidates. A repeated numeric footer candidate (for
example a journal date) can be removed together with the trailing margin block. Matching text inside an article body
remains operative content. This corrects a pre-alpha defect that removed repeated
body sentences as if they were headers; affected document text, offsets and IDs
can consequently change.

This is a conservative text-context heuristic, not a bounding-box margin contract.
Unpunctuated body text at a page start can still be ambiguous. Other profile noise,
running-header and TOC rules remain separate. Explicit cleanup/exclusion decisions
now have [removal traces](tracing.md); normalization and merges remain partially
instrumented. Use original-source review when cleanup affects difficult documents.

## Adapter boundaries and reproducibility

Both backends return internal extractor-neutral page text records to shared PDF
cleanup. Native raised digit spans are preserved as Unicode superscripts using
font evidence; the text engine converts them to dotted numbering only next to legal
markers. Ordinary mathematical scripts are preserved in the document text plane.

The layout adapter calls PyMuPDF4LLM `to_text(page_chunks=True)`, avoiding Markdown
presentation syntax in legal detectors. Extractor page chunks are source page records,
not legal chunks. Header/footer content is requested and then passes through the
existing contextual cleanup. The adapter does not claim faithful tables or a full
layout/provenance model; `Chunk.page` still has no end-to-end assignment.

PyMuPDF4LLM activates global layout state and emits global parser diagnostics. Its
adapter runs in a dedicated subprocess with a temporary working directory to isolate
these effects from host calls and keep CLI JSON clean. It uses the caller's Python
installation, does not toggle global layout modes in the host, and does not save the
source PDF. Process startup adds overhead; PyMuPDF remains the default fast path.
An unavailable or failing selected backend raises an error; it never silently
switches extraction engines.

OCR renders selected pages at the requested DPI and replaces their in-memory text
with a recognized text overlay. Auto can therefore re-recognize native portions of
a mixed page. Blank pages are valid. In 1.28.2, the upstream to_text wrapper does not
forward ocr_dpi into its parser, so the callback explicitly honors our setting.

Trace records backend/package versions, requested OCR mode, actual OCR page events,
language, DPI and traineddata SHA-256 hashes. Mode auto alone is not evidence that
OCR ran. Keep input, settings, package/model versions and assets fixed when comparing
results; OCR/layout outputs can vary across environments and releases. Explainability
of legal decisions does not imply perfect OCR recognition.

API/CLI details and errors are in [api.md](api.md). Local data/tests are described in
[development.md](development.md). Upstream sources:
[PyMuPDF4LLM API](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html),
[PyMuPDF OCR](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html),
[Tesseract language data](https://github.com/tesseract-ocr/tessdata_fast).
