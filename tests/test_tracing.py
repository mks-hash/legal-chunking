"""Decision evidence from the runtime, with source-plane and output checks."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from legal_chunking import chunk_pdf, chunk_text
from legal_chunking.detect.headings import detect_heading
from legal_chunking.extract.pdf_runtime import normalize_page_raw_text, trim_us_rules_body_pages
from legal_chunking.extract.pdf_types import PdfPageText
from legal_chunking.tracing import TraceCollector, TraceStage


@pytest.mark.parametrize(
    "path",
    sorted((Path(__file__).parent / "fixtures" / "quality").glob("*.json")),
    ids=lambda p: p.stem,
)
def test_trace_preserves_reviewed_document_and_is_repeatable(path: Path) -> None:
    case = json.loads(path.read_text())
    args = {"profile": case["profile"], "doc_kind": case["doc_kind"], "source_name": path.name}
    text = case.get("input_text", case["text"])
    traced = chunk_text(text, **args, trace=True)
    assert replace(traced, trace=None) == chunk_text(text, **args)
    assert traced == chunk_text(text, **args, trace=True)


@pytest.mark.parametrize(
    "text,profile,policy,rule",
    [
        ("1. lower case", "generic", "statute", "heading.numeric.lowercase_title"),
        ("1 The notice", "generic", "statute", "heading.numeric.missing_marker"),
        ("Rule 2. The notice", "us", "statute", "heading.rule.weak_pronoun"),
        ("Article 2(1) TFEU", "eu", "statute", "heading.article.parenthesized_title"),
        ("M. SCHULZ", "eu", "statute", "heading.roman_heading.signature_name"),
        ("a. General principles", "ae", "statute", "heading.alpha_heading.lowercase_marker"),
        ("Article 1. Scope", "generic", "guidance", "heading.article.guidance_policy"),
        ("1.2 Scope", "generic", "guidance", "heading.numeric.guidance_depth"),
    ],
)
def test_matched_heading_rejection_explains_actual_rule(
    text: str, profile: str, policy: str, rule: str
) -> None:
    trace = TraceCollector()
    assert (
        detect_heading(text, profile=profile, chunk_policy=policy, trace=trace, offset=25) is None
    )
    events = [e for e in trace.to_report().events if e.type == "heading_candidate_rejected"]
    assert rule in [e.data["rule_id"] for e in events]
    for event in events:
        assert event.stage == TraceStage.DETECT
        assert event.data["text"] == text
        assert event.data["offset"] == 25
        assert event.data["reason"]


def test_unmatched_body_is_not_claimed_as_rejected_heading() -> None:
    trace = TraceCollector()
    assert detect_heading("The clerk retained the record.", trace=trace) is None
    assert trace.to_report().events == ()


def test_numeric_candidate_is_rejected_by_article_context_with_correct_offset() -> None:
    text = "Article 1. Scope\n1. General rule\nThe notice is retained.\nArticle 2. Records"
    doc = chunk_text(text, trace=True)
    rejected = [e for e in doc.trace.events if e.type == "heading_candidate_rejected"]
    context = next(
        e for e in rejected if e.data["rule_id"] == "heading.context.article_body_numeric"
    )
    assert context.data["text"] == "1. General rule"
    assert context.data["offset"] == text.index("1. General rule")
    assert context.data["candidate_label"] == "Section 1. General rule"
    accepted = [e for e in doc.trace.events if e.type == "heading_detected"]
    assert [e.data["label"] for e in accepted] == ["Article 1. Scope", "Article 2. Records"]
    assert all(e.data["rule_id"] == "section.heading.accepted" for e in accepted)
    assert "1. General rule" in doc.sections[1].text


def test_pdf_margin_and_classified_deletions_have_page_and_original_line_numbers(
    tmp_path: Path,
) -> None:
    import pymupdf

    path = tmp_path / "registry.pdf"
    with pymupdf.open() as pdf:
        for number in range(1, 4):
            pdf.new_page().insert_text(
                (72, 72),
                f"Registry Bulletin\nArticle {number}. Notices\n"
                f"A notice must identify its sender.\nRegistry Journal\n{number}",
            )
        pdf.save(path)
    before = path.read_bytes()
    traced = chunk_pdf(path, trace=True)
    assert replace(traced, trace=None) == chunk_pdf(path)
    assert path.read_bytes() == before
    removals = [e.data for e in traced.trace.events if e.type == "pdf_text_removed"]
    for number in range(1, 4):
        page = [e for e in removals if e["page_number"] == number]
        assert any(
            e["rule_id"] == "pdf.margin.repeated_leading" and e["line_number"] == 1 for e in page
        )
        assert any(e["rule_id"] == "pdf.line.page_number" and e["line_number"] == 5 for e in page)
    assert all(e["input_stage"] == "normalized_page_lines" for e in removals)
    assert not any(e["text"] == "A notice must identify its sender." for e in removals)
    assert traced.text.count("A notice must identify its sender.") == 3


def test_profile_rule_and_trailing_margin_deletions_record_actual_policy_match() -> None:
    text = "Article 1. Notices\nA notice is retained.\n4.5.2016\nRegistry Journal\nEN"
    trace = TraceCollector()
    args = {"profile": "eu", "repeated_noise": {"4.5.2016", "Registry Journal"}}
    result = normalize_page_raw_text(text, **args, trace=trace, page_number=8)
    assert result == normalize_page_raw_text(text, **args)
    assert result == "Article 1. Notices\nA notice is retained."
    removals = [e.data for e in trace.to_report().events if e.type == "pdf_text_removed"]
    profile = next(e for e in removals if e["reason"] == "profile_noise")
    assert (profile["text"], profile["line_number"], profile["page_number"]) == ("EN", 5, 8)
    assert profile["policy_field"] == "drop_line_equals"
    assert profile["policy_value"] == "EN"
    footer = [e for e in removals if e["rule_id"] == "pdf.margin.repeated_trailing"]
    assert [(e["text"], e["line_number"]) for e in footer] == [
        ("4.5.2016", 3),
        ("Registry Journal", 4),
    ]


def test_toc_page_exclusion_is_an_aggregate_runtime_decision() -> None:
    text = "Contents\nArticle 1 ........ 2\nArticle 2 ........ 3"
    trace = TraceCollector()
    assert normalize_page_raw_text(text, profile="generic", trace=trace, page_number=4) == ""
    (event,) = [e for e in trace.to_report().events if e.type == "pdf_page_removed"]
    assert event.data["rule_id"] == "pdf.page.toc_leader_cluster"
    assert event.data["toc_leader_count"] == 2
    assert event.data["page_number"] == 4
    assert event.data["text"] == text


def test_us_document_front_matter_and_prefix_report_cleaned_text_plane() -> None:
    body = (
        "Foreword.\nRULES OF CIVIL PROCEDURE FOR THE UNITED STATES DISTRICT COURTS\n"
        "Rule 1. Scope and Purpose"
    )
    pages = [PdfPageText(2, "TABLE OF CONTENTS"), PdfPageText(6, body)]
    trace = TraceCollector()
    result = trim_us_rules_body_pages(pages, trace=trace)
    assert result == trim_us_rules_body_pages(pages)
    assert pages[1].text == body
    page_event, prefix_event = trace.to_report().events
    assert page_event.data["rule_id"] == "pdf.document.us_rules_front_matter"
    assert page_event.data["page_number"] == 2
    assert prefix_event.data["rule_id"] == "pdf.document.us_rules_body_prefix"
    assert prefix_event.data["page_number"] == 6
    assert prefix_event.data["input_stage"] == "cleaned_page_text"
    assert (
        body[prefix_event.data["start_offset"] : prefix_event.data["end_offset"]] == "Foreword.\n"
    )


def test_us_running_rule_trim_reports_actual_removed_prefix() -> None:
    trace = TraceCollector()
    text = "1\nFEDERAL RULES OF CIVIL PROCEDURE\nRule 4\n(a) The clerk retains a copy."
    result = normalize_page_raw_text(text, profile="us", trace=trace, page_number=12)
    assert result == normalize_page_raw_text(text, profile="us")
    events = [e.data for e in trace.to_report().events if e.type == "pdf_text_removed"]
    assert [(e["text"], e["line_number"]) for e in events] == [
        ("1", 1),
        ("FEDERAL RULES OF CIVIL PROCEDURE", 2),
        ("Rule 4", 3),
    ]
    assert {e["rule_id"] for e in events} == {"pdf.margin.us_running_rule"}
    assert all(e["page_number"] == 12 for e in events)
    assert "The clerk retains a copy." in result


def test_profile_regex_removal_records_matching_asset_pattern() -> None:
    trace = TraceCollector()
    text = "Article 1. Scope\nA copy is retained.\nL 119/2"
    result = normalize_page_raw_text(text, profile="eu", trace=trace)
    assert result == "Article 1. Scope\nA copy is retained."
    (event,) = [e.data for e in trace.to_report().events if e.type == "pdf_text_removed"]
    assert event["line_number"] == 3
    assert event["policy_field"] == "drop_line_regexes"
    assert event["policy_value"] == r"^[CL]\s+\d+/\d+$"


def test_duplicate_margin_text_in_body_is_not_recorded_as_deleted() -> None:
    trace = TraceCollector()
    text = "Registry Bulletin\nArticle 1. Scope\nRegistry Bulletin\nA copy is retained."
    result = normalize_page_raw_text(
        text, profile="generic", repeated_noise={"Registry Bulletin"}, trace=trace
    )
    events = [e.data for e in trace.to_report().events if e.type == "pdf_text_removed"]
    assert [(e["text"], e["line_number"]) for e in events] == [("Registry Bulletin", 1)]
    assert "Registry Bulletin A copy is retained." in result


def test_rejected_prefixed_subcandidate_can_precede_an_accepted_alternative() -> None:
    text = "Opening.\nVII. Part I - lower case"
    doc = chunk_text(text, profile="ae", trace=True)
    rejected = [e for e in doc.trace.events if e.type == "heading_candidate_rejected"]
    child = next(e for e in rejected if e.data["detector"] == "part")
    assert child.data["rule_id"] == "heading.part.lowercase_title"
    assert child.data["text"] == "Part I - lower case"
    assert child.data["offset"] == text.index("Part I")
    (accepted,) = [e for e in doc.trace.events if e.type == "heading_detected"]
    assert accepted.data["offset"] == text.index("VII.")
    assert accepted.data["label"] == "Section VII. Part I - lower case"
    assert replace(doc, trace=None) == chunk_text(text, profile="ae")
