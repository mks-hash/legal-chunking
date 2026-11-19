"""Reproducible throughput and peak-memory benchmarks for legal-chunking."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import asdict, dataclass

from legal_chunking import ExtractedPage, analyze_references, chunk_pages, chunk_text

ALL_PROFILES: tuple[str, ...] = ("generic", "ru", "us", "eu", "ae")


@dataclass(slots=True, frozen=True)
class BenchmarkResult:
    profile: str
    operation: str
    input_bytes: int
    median_ms: float
    throughput_mb_s: float
    peak_kib: float
    output_count: int


def _build_article_block(profile: str, idx: int) -> str:
    prev_idx = max(1, idx - 1)
    if profile == "ru":
        return (
            f"Статья {idx}. Порядок исполнения обязательств\n"
            f"1. Стороны исполняют обязательства в соответствии с пунктами 1 и 3 "
            f"статьи {idx} ГК РФ и статьей 225¹⁶⁻¹ АПК РФ.\n"
            f"2. При нарушении условий применяются правила статьи {prev_idx} ГК РФ "
            f"и части 2 статьи {idx} настоящего Кодекса."
        )
    if profile == "us":
        return (
            f"Rule {idx}. Scope and Civil Procedure\n"
            f"(a) General. Jurisdiction arises under 28 U.S.C. § {1300 + idx} and "
            f"17 C.F.R. § 240.{idx}.\n"
            f"(b) Cross-Reference. Subject to Rule {prev_idx}(a)(1), notice is required."
        )
    if profile == "eu":
        return (
            f"Article {idx}. Lawfulness of processing\n"
            f"1. Processing shall be lawful only under Article {idx}(1)(a) GDPR.\n"
            f"2. Member States may maintain provisions referred to in Article {prev_idx}(2) GDPR."
        )
    if profile == "ae":
        return (
            f"1.{idx}.1 Rule\n"
            f"An Authorised Firm must comply with Rule 1.{idx}.1 and Article {prev_idx} "
            f"of the DIFC Regulatory Law.\n"
            f"Guidance\n"
            f"See also Rule 1.{prev_idx}.1 for reporting obligations."
        )
    return (
        f"Article {idx}. General provisions\n"
        f"1. Each party shall perform its obligations in accordance with Article {idx}.\n"
        f"2. Remedies for breach are governed by Article {prev_idx} of this agreement."
    )


def build_synthetic_document(profile: str, unit_count: int) -> tuple[str, list[ExtractedPage]]:
    """Build a deterministic multi-page synthetic legal text for the given profile."""
    pages: list[ExtractedPage] = []
    units_per_page = 5
    for page_index in range(0, unit_count, units_per_page):
        page_number = (page_index // units_per_page) + 1
        blocks = [
            _build_article_block(profile, idx)
            for idx in range(page_index + 1, min(unit_count, page_index + units_per_page) + 1)
        ]
        pages.append(ExtractedPage(page_number=page_number, text="\n\n".join(blocks)))
    full_text = "\n\n".join(page.text for page in pages)
    return full_text, pages


def measure(
    profile: str,
    operation: str,
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
        profile=profile,
        operation=operation,
        input_bytes=input_bytes,
        median_ms=median_s * 1000.0,
        throughput_mb_s=throughput,
        peak_kib=peak_bytes / 1024.0,
        output_count=output_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run legal-chunking core benchmarks.")
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=ALL_PROFILES,
        default=list(ALL_PROFILES),
        help="Profiles to benchmark (default: all enabled profiles).",
    )
    parser.add_argument(
        "--articles",
        type=int,
        default=100,
        help="Number of synthetic units per profile (default: 100).",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="Number of timed repetitions per benchmark (default: 5).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a formatted table.",
    )
    args = parser.parse_args()

    results: list[BenchmarkResult] = []
    for profile in args.profiles:
        full_text, pages = build_synthetic_document(profile, args.articles)
        input_bytes = len(full_text.encode("utf-8"))
        results.extend(
            [
                measure(
                    profile,
                    "chunk_text",
                    input_bytes,
                    args.repeats,
                    lambda t=full_text, p=profile: len(
                        chunk_text(t, profile=p, source_name=f"bench-{p}.txt").chunks
                    ),
                ),
                measure(
                    profile,
                    "chunk_pages",
                    input_bytes,
                    args.repeats,
                    lambda ps=pages, p=profile: len(
                        chunk_pages(ps, profile=p, source_name=f"bench-{p}.txt").chunks
                    ),
                ),
                measure(
                    profile,
                    "analyze_references",
                    input_bytes,
                    args.repeats,
                    lambda t=full_text, p=profile: len(
                        analyze_references(t, profile=p).occurrences
                    ),
                ),
            ]
        )

    env = {
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.machine()}",
        "articles": args.articles,
        "repeats": args.repeats,
    }
    if args.json:
        print(json.dumps({"environment": env, "results": [asdict(r) for r in results]}, indent=2))
        return

    print(f"Environment: Python {env['python']} on {env['platform']}")
    print(f"Config: {args.articles} units/profile, {args.repeats} timed repeats")
    print()
    print(
        f"{'Profile':<8} {'Operation':<20} {'Input KiB':>10} {'Median (ms)':>12} "
        f"{'Throughput':>13} {'Peak KiB':>10} {'Items':>7}"
    )
    print("-" * 86)
    for item in results:
        print(
            f"{item.profile:<8} {item.operation:<20} {item.input_bytes / 1024:>10.1f} "
            f"{item.median_ms:>12.2f} {item.throughput_mb_s:>10.2f} MB/s "
            f"{item.peak_kib:>10.1f} {item.output_count:>7}"
        )


if __name__ == "__main__":
    main()
