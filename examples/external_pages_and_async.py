"""Runnable integration patterns for legal-chunking (zero external dependencies).

Demonstrates:
1. Feeding page-bounded text from an external extractor (e.g. Docling, Unstructured,
   Azure DI, or a custom OCR pipeline) into ``chunk_pages`` to preserve ``Chunk.page``.
2. Running ``analyze_references`` over materialized chunks for source-anchored citations.
3. Offloading synchronous CPU-bound chunking cleanly inside an ``asyncio`` service via
   ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio

from legal_chunking import ExtractedPage, analyze_references, chunk_pages, chunk_text


def demo_external_pages() -> None:
    pages = [
        ExtractedPage(
            page_number=1,
            text="Article 1. Scope\n1. This Regulation applies to processing of personal data.",
        ),
        ExtractedPage(
            page_number=2,
            text=(
                "Article 6. Lawfulness of processing\n"
                "1. Processing shall be lawful only under Article 6(1)(a) GDPR."
            ),
        ),
    ]
    document = chunk_pages(pages, profile="eu", source_name="gdpr-excerpt.pdf")
    print("=== External pages -> chunk_pages ===")
    for chunk in document.chunks:
        refs = analyze_references(chunk.text, profile="eu")
        print(
            f"page={chunk.page} order={chunk.order} method={chunk.chunk_method} "
            f"article={chunk.metadata.article_number} refs={len(refs.occurrences)}"
        )


async def demo_asyncio_service() -> None:
    docs = [
        ("ru", "Статья 450. Основания изменения договора\n1. См. пункты 1 и 3 статьи 450 ГК РФ."),
        ("us", "Rule 1. Scope and Purpose\n(a) Jurisdiction under 28 U.S.C. § 1331."),
    ]
    results = await asyncio.gather(
        *(
            asyncio.to_thread(chunk_text, text, profile=profile, source_name=f"{profile}.txt")
            for profile, text in docs
        )
    )
    print("\n=== Asyncio service -> asyncio.to_thread ===")
    for doc in results:
        print(f"profile={doc.profile} policy={doc.chunk_policy} chunks={len(doc.chunks)}")


def main() -> None:
    demo_external_pages()
    asyncio.run(demo_asyncio_service())


if __name__ == "__main__":
    main()
