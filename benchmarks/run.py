"""Reproducible throughput and peak-memory benchmarks for legal-chunking."""

from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass

from legal_chunking import ExtractedPage, analyze_references, chunk_pages, chunk_text


@dataclass(slots=True, frozen=True)
class BenchmarkResult:
    name: str
    input_bytes: int
    median_ms: float
    throughput_mb_s: float
    peak_kib: float
    output_count: int


def build_synthetic_ru_statute(article_count: int) -> tuple[str, list[ExtractedPage]]:
    """Build a deterministic multi-page Russian statute with compound citations."""
    pages: list[ExtractedPage] = []
    articles_per_page = 5
    for page_index in range(0, article_count, articles_per_page):
        page_number = (page_index // articles_per_page) + 1
        blocks: list[str] = []
        for idx in range(page_index + 1, min(article_count, page_index + articles_per_page) + 1):
            blocks.append(
                f"Статья {idx}. Порядок исполнения обязательств\n"
                f"1. Стороны исполняют обязательства в соответствии с пунктами 1 и 3 "
                f"статьи {idx} ГК РФ и статьей 225¹⁶⁻¹ АПК РФ.\n"
                f"2. При нарушении условий применяются правила статьи {max(1, idx - 1)} ГК РФ "
                f"и части 2 статьи {idx} настоящего Кодекса."
            )
        pages.append(ExtractedPage(page_number=page_number, text="\n\n".join(blocks)))
    full_text = "\n\n".join(page.text for page in pages)
    return full_text, pages


def measure(
    name: str,
    input_bytes: int,
    repeats: int,
    fn: Callable[[], int],
) -> BenchmarkResult:
    # Warm up caches before timing.
    output_count = fn()
    timings: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        output_count = fn()
        timings.append(time.perf_counter() - start)

    tracemalloc.start()
    fn()
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    median_s = statistics.median(timings)
    throughput = (input_bytes / (1024 * 1024)) / median_s if median_s > 0 else 0.0
    return BenchmarkResult(
        name=name,
        input_bytes=input_bytes,
        median_ms=median_s * 1000.0,
        throughput_mb_s=throughput,
        peak_kib=peak_bytes / 1024.0,
        output_count=output_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run legal-chunking core benchmarks.")
    parser.add_argument(
        "--articles",
        type=int,
        default=200,
        help="Number of synthetic articles to generate (default: 200).",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="Number of timed repetitions per benchmark (default: 5).",
    )
    args = parser.parse_args()

    full_text, pages = build_synthetic_ru_statute(args.articles)
    input_bytes = len(full_text.encode("utf-8"))

    results = [
        measure(
            "chunk_text (ru statute)",
            input_bytes,
            args.repeats,
            lambda: len(chunk_text(full_text, profile="ru", source_name="bench.txt").chunks),
        ),
        measure(
            "chunk_pages (ru statute)",
            input_bytes,
            args.repeats,
            lambda: len(chunk_pages(pages, profile="ru", source_name="bench.txt").chunks),
        ),
        measure(
            "analyze_references (ru)",
            input_bytes,
            args.repeats,
            lambda: len(analyze_references(full_text, profile="ru").occurrences),
        ),
    ]

    print(
        f"Environment: Python {sys.version.split()[0]} on {platform.system()} {platform.machine()}"
    )
    print(
        f"Input: {args.articles} articles, {len(pages)} pages, {input_bytes / 1024:.1f} KiB UTF-8"
    )
    print()
    print(f"{'Benchmark':<28} {'Median (ms)':>12} {'Throughput':>14} {'Peak KiB':>10} {'Items':>8}")
    print("-" * 76)
    for item in results:
        print(
            f"{item.name:<28} {item.median_ms:>12.2f} "
            f"{item.throughput_mb_s:>11.2f} MB/s {item.peak_kib:>10.1f} {item.output_count:>8}"
        )


if __name__ == "__main__":
    main()
