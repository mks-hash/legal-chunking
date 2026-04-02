# Project Scope

## Goal

`legal-chunking` is an open-source Python library for deterministic, structure-aware chunking of legal documents.

The library focuses on one problem:

- accept legal text from plain text and PDF sources
- normalize text deterministically
- detect structural boundaries such as headings, articles, sections, clauses, and paragraphs
- build chunks from logical legal boundaries instead of fixed-size windows
- return stable structured metadata for downstream processing

## Non-Goals

This project does not provide:

- embeddings
- vector databases
- retrieval orchestration
- LLM integrations
- web services
- UI
- workflow engines

## Principles

- deterministic outputs for identical inputs
- structure-aware chunking over naive sliding windows
- asset-driven profiles over hardcoded jurisdiction logic
- small public API with stable models
- testable chunk-boundary behavior

## Current Status

The repository is in bootstrap stage.

Current baseline:

- Python 3.14+
- packaging via Hatchling
- pytest and Ruff configured
- initial package, CLI, and test scaffold in place

## Near-Term Direction

The next public milestones are:

1. deterministic normalization and hashing
2. asset-backed profile resolution
3. heading and section detection
4. structure-aware chunk assembly
5. PDF extraction boundary
6. golden fixtures and regression evaluation
