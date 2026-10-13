<!--
SYNC IMPACT REPORT (temporary, remove before committing)

Version change: 2.1.0 → 2.2.0 (MINOR: materially expanded guidance in Principles III and V and in
Technical Constraints and Development Workflow; no principle removed or redefined)

Amendment record 2.2.0 (2026-10-13):
- Proposal: align the constitution with decisions made in specs/001-contract-review-mvp and
  plan.md since 2.1.0:
  (a) Principle III: pattern-based (heuristic) findings, used for missing mandatory elements
      (plan R10), MUST be labeled as heuristic and flagged for manual review.
  (b) Principle V: generated reports are stored locally for 30 days (spec §4, AC15), without contract
      text; retrieval is by report_id only; external exposure of the service requires authentication.
  (c) Technical Constraints: the two persistent stores (Chroma for norms, SQLite for reports) and the
      quality tooling (pytest-cov; Codecov and Code Climate receive source and coverage reports only).
  (d) Development Workflow: required_element patterns are tested on synthetic contracts before merge;
      CI runs on GitHub Actions; the list of uncommitted artifacts is extended (.env, data/reports.db,
      coverage.xml, .venv, data/chroma, __pycache__).
- Approval: given by the project owner, who requested this amendment on 2026-10-13.
- Migration note: no existing client data, KB records, or index formats are changed. The reports store
  and the CI configuration are new files; no re-processing is required. Existing `.gitignore` already
  covers the uncommitted artifacts listed in (d).

Amendment record 2.1.0 (2026-10-13):
- Proposal: name the external generative LLM provider in Principle V (Anthropic, Claude; model set
  in configuration), and require verification of the provider's data-retention and training terms
  before the first real client contract is sent. Reason: the 2.0.0 approval did not name a provider,
  and the feature plan (specs/001-contract-review-mvp/plan.md, R3) needs one.
- Approval: given by the project owner, who requested this amendment on 2026-10-13.
- Migration note: no existing records, index, or file formats are affected; no client data has
  been sent externally yet. The retention/training verification is a precondition for the first
  real client contract, recorded in plan.md (R3). Changing the provider requires a further amendment.

Previous amendment record (2026-10-13, version 2.0.0):
- Proposal: permit sending client contract text to the external generative LLM service, needed
  for Phase 0 of the MVP in specs/001-contract-review-mvp.
- Approval: given by the project owner, option C ("external cloud API approved for all data").
- Migration note: no existing records, index, or file formats are affected; no client data has
  been sent externally yet, so no re-processing is required.

Previous version history: template scaffold (unversioned) → 1.0.0 (initial ratification) → 2.0.0
Basis: no user principle input was supplied; principles were inferred from the existing
code in src/ (ingest/, kb/) and data/laws/ (Argentine civil-code KB with validity dates).

Modified principles (template placeholder → new title):
- [PRINCIPLE_1_NAME] → I. Source-Grounded Legal Claims
- [PRINCIPLE_2_NAME] → II. Temporal Validity of Law
- [PRINCIPLE_3_NAME] → III. Advisory Output, Human Decision
- [PRINCIPLE_4_NAME] → IV. Verifiable Pipeline Stages
- [PRINCIPLE_5_NAME] → V. Confidential Client Data

Added sections:
- Technical Constraints (replaces [SECTION_2_NAME])
- Development Workflow (replaces [SECTION_3_NAME])

Removed sections: none

Deferred TODOs:
- TODO(RATIFICATION_DATE): no record of the original adoption date in the repo. Set it
  when the project owner confirms the date.
- TODO(GUIDANCE_FILE): no runtime guidance file (e.g. CLAUDE.md) is referenced yet.
- Observed code gap (not a constitution change): src/kb/index.py stores open-ended
  valid_to as "" (clean() maps None → ""), while src/kb/check.py filters with string
  comparisons on valid_to. Principle II requires the integer sentinel 99991231; the
  indexing and query code must be aligned in a follow-up task.
-->

# Contrato Review Constitution

## Core Principles

### I. Source-Grounded Legal Claims (NON-NEGOTIABLE)
Every statement about what the law requires, permits, or prohibits MUST be traceable to a
record in the knowledge base (`data/laws/`, indexed in `data/chroma`). Each cited record MUST
carry its `regime`, `article`, and `source_url`. The system MUST NOT generate legal text,
article numbers, or regime references from model memory. When retrieval returns no
applicable record, the output MUST say so explicitly instead of filling the gap. Records
marked `verbatim: true` MUST be quoted without alteration.

Rationale: a contract review is only useful if each conclusion can be checked against the
primary source. Unsourced legal claims are a correctness and liability risk.

### II. Temporal Validity of Law
Legal retrieval MUST be filtered by the validity period in force on the contract's relevant
date (signing date, or the date specified by the reviewer), not by the current date. Records
with an open-ended `valid_to` MUST be represented with the integer sentinel `99991231` in
filterable fields (see `src/kb/dates.py`). Empty strings MUST NOT be used as a stand-in for
an open-ended date in any field used for range filtering.

Rationale: the same clause can be lawful under one regime and void under another. Applying
the wrong version of an article to a contract produces a wrong review.

### III. Advisory Output, Human Decision
The system produces review aids: highlighted risks, relevant articles, and open questions.
It MUST NOT present its output as a final legal opinion. Any review output MUST state that a
qualified lawyer makes the final determination. Where confidence is low, the ambiguity MUST
be surfaced to the reader rather than resolved silently. Findings produced by pattern-based
(heuristic) checks, such as missing mandatory elements, MUST be labeled as heuristic and flagged
for manual review; they MUST NOT be presented as established legal conclusions.

Rationale: the tool supports professional judgment; it does not replace it, and the output
must make that boundary visible.

### IV. Verifiable Pipeline Stages
Each ingestion stage (`extract` → `split` → `meta` → `index` → `check`) MUST be runnable and
inspectable on its own. Changes to a stage MUST be verified against at least one real or
representative sample document before merge. Scanned PDFs flagged `needs_ocr` MUST NOT be
silently treated as complete text; they MUST go through the OCR fallback or be reported as
unprocessed. Heuristics (contract-type detection, signing-date detection) MUST document their
failure modes in code comments or the spec.

Rationale: extraction and classification errors propagate silently into legal retrieval.
Each stage must be checkable so that errors are found where they originate.

### V. Confidential Client Data
Contract documents supplied for review are client-confidential. Retrieval and indexing of
legal records MUST run locally. The text of client contracts MAY be sent to the external
generative language model service approved by the project owner for all client contract data
(approval recorded 2026-10-13). The approved provider is Anthropic (Claude); the model is set in
configuration. Before the first real client contract is sent, the provider's data-retention and
model-training terms for the project's API account MUST be verified and recorded in the feature
plan. Changing the provider requires a further amendment. No other external service may receive
client contract data without a separate owner approval. Secrets (for example `HF_TOKEN` and
`ANTHROPIC_API_KEY` in `.env`) MUST NOT be committed, pasted into specs, plans, or logs, or
included in test fixtures. Sample
contracts used in tests or docs MUST be synthetic or fully anonymized.

Generated review reports MAY be stored locally for 30 days so that they can be retrieved by
`report_id` and rendered in another language. A stored report MUST NOT contain contract text beyond
clause identifiers and headings, MUST be deleted when its retention period ends, and MUST NOT be
readable through any external exposure of the service until that exposure is authenticated.

Rationale: contracts contain personal data and commercial terms. A leak is irreversible.

## Technical Constraints

- Language and runtime: Python 3.11 in the project-local `.venv`. Dependencies MUST be
  declared and pinned before a feature is considered complete.
- Document parsing: PyMuPDF (`fitz`) for PDF and `python-docx` for DOCX. OCR (`pytesseract`,
  `pdf2image`, system `tesseract`) is an optional fallback and MUST NOT be a hard dependency
  of the core path.
- Embeddings: `intfloat/multilingual-e5-large`. Passages MUST be encoded with the
  `passage: ` prefix and queries with the `query: ` prefix. Mixing prefixes or models
  invalidates the index and requires a full re-index.
- Vector store: ChromaDB persistent client at `data/chroma`, collection `ar_law`, cosine
  space. Changing the embedding model, collection metadata, or record ID scheme requires a
  full re-index, and the change MUST be recorded in the spec.
- Record IDs: `{regime}-{article}`. Changing this scheme MUST be treated as a breaking change.
- Persistent stores: ChromaDB holds legal norms (`data/chroma`); SQLite (`data/reports.db`) holds
  stored reports only, with the retention rule from Principle V. Client contract text is never
  written to either store.
- Quality tooling: coverage is measured with `pytest-cov`. Codecov and Code Climate receive source
  code and coverage reports only; `data/`, `.env`, and `.venv/` are excluded in their configs.
- Languages: the project processes Spanish source material and multilingual code comments.
  Legal terms MUST be kept in the source language in stored records and quotes.

## Development Workflow

- Features follow the Spec Kit flow: specify → clarify (when needed) → plan → tasks →
  implement → analyze. Changes that affect legal retrieval, validity filtering, or the
  knowledge-base schema MUST have a spec entry before implementation.
- Every change touching `src/kb/` or `src/ingest/` MUST include a verification step: either
  a check query run (see `src/kb/check.py`) or a documented manual run on a sample document,
  with the result recorded in the PR or task notes.
- Knowledge-base JSON files in `data/laws/` MUST be edited with their `source_url` and
  validity dates intact. Each new or changed record MUST be reviewed against the source
  before it is indexed.
- Generated and sensitive artifacts MUST NOT be committed: `.env`, `.venv/`, `__pycache__/`,
  `data/chroma/`, `data/reports.db`, `coverage.xml`. Ignore rules live in `.gitignore`; `.env.example`
  (without values) is the committed template.
- Heuristic patterns (for example, `required_element` patterns in the knowledge base) MUST be tested
  before merge on synthetic contracts with known presence and absence of each element, and their
  failure modes MUST be documented next to the patterns (Principle IV).
- Continuous integration runs on GitHub Actions (`.github/workflows/ci.yml`): unit and contract tests
  with coverage. Integration tests that need the built index and the local embedding model run
  locally. CI secrets (such as `CODECOV_TOKEN`) are stored in the CI secret store, not in the repository.
- Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).

## Governance

This constitution supersedes other project practices where they conflict. Every spec, plan,
and task review MUST check compliance with Principles I–V; a violation MUST be resolved or
explicitly justified in the plan's complexity or deviation section before implementation.

Amendments require: (1) a written proposal describing the change and its reason, (2) approval
by the project owner, (3) an updated Sync Impact Report, and (4) a migration note for any
change that affects existing records, the index, or the file formats.

Versioning policy (semantic versioning):
- MAJOR: removal or redefinition of a principle in a way that changes how existing output or
  data must be handled (for example, dropping the source-grounding requirement).
- MINOR: a new principle or section, or materially expanded guidance.
- PATCH: wording clarifications, typo fixes, and non-semantic refinements.

Compliance review: each PR or feature review MUST confirm that legal claims are source-grounded,
that date filtering uses the validity period in force, and that no client data or secrets are
exposed. The constitution is reviewed at least once per major feature cycle.

**Version**: 2.2.0 | **Ratified**: TODO(RATIFICATION_DATE): original adoption date not recorded in the repo | **Last Amended**: 2026-10-13
