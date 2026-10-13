# PRODUCT-SPEC — Phase 0: Contract Review MVP (Buenos Aires / CABA)

## 1. Overview
A web application that lets a user upload a residential **sale (compraventa)** or
**lease (locación)** contract (Spanish) and returns a structured review: flagged
risks, missing clauses, and mismatches against the law applicable **in the
Autonomous City of Buenos Aires (CABA)**. Phase 0 uses **a knowledge base of legal
norms together with a generative language model** only (no fine-tuning, no classifier yet).

Scope note: contract validity is governed by **national** law (Código Civil y
Comercial + DNU 70/2023 / Ley 27.551). CABA adds a **local fiscal layer** — mainly
the stamp tax (impuesto de sellos). Other provinces are out of scope.

## Clarifications

### Session 2026-10-13

- Q: Should phase 0 recognize scanned PDFs via OCR, or is it enough to reject scans with a clear message? → A: OCR as an optional fallback: if it is available, scans are recognized; otherwise a clear error is returned without a report.
- Q: For a lease, should the system calculate the CABA stamp-tax amount, or is it enough to state that the tax applies and who pays it? → A: For a lease, only whether the tax applies and who pays it, without an amount, until the rate is confirmed.
- Q: Should the signing date select the legal regime for sale contracts as well as leases, or is one regime enough for sales regardless of date? → A: The signing date selects the regime for both sales and leases, using the validity periods of the norms in the knowledge base.
- Q: How long should the system keep the uploaded contract and the generated report? → A: Delete the contract immediately after the report is generated; the contract text is not kept in logs.
- Q: If contract clauses fall under different legal regimes, should the regime be chosen once by signing date for the whole contract or per clause? → A: One regime for the whole contract, chosen by signing date.
- Q: What confidence threshold triggers manual review of a clause (AC10)? → A: If the best relevance score of the norms for a clause is below 0.3, the clause goes to manual review; the threshold is refined after the first run. (owner's decision, outside the question limit)
- Q: Are reference contracts (modelo de contrato) needed in phase 0? → A: No; the comparison is only against legal norms; reference contracts will be added later. (owner's decision, outside the question limit)
- Q: What to do with the lease stamp-tax rate while it is unconfirmed? → A: Mark it as pending until it is confirmed from the Ley Tarifaria 2026. (owner's decision, outside the question limit)
- Q: How should the report disclaimer read: is the product only informational, or must it also say that a qualified lawyer makes the final decision? → A: The report states that it is informational and that a qualified lawyer makes the final decision.
- Q: What does the system do if the external generative-model service is unavailable or returns an error during analysis? → A: Several automatic retries; if the failure persists, a clear error with no partial report.
- Q: Which statistic should verify the goal "a 10-clause contract is processed in less than 60 seconds"? → A: 95% of runs for contracts of up to 10 clauses finish within 60 seconds.
- Q: How much contract text is sent to the external generative-model service per request? → A: One clause together with the norms found for it.
- Q: Where is the generated report kept after the contract is deleted? → A: The report is available for download only in the current session; no server-side copy is kept.
- Q: Which external generative-model service is used for clause analysis and translation? → A: A cloud service approved by the owner for client data; the specific provider is recorded in the plan. The provider's data-retention and training terms are verified before the first real contract. (owner's decision, outside the question limit)
- Q: How are missing mandatory clauses (UC3) checked if each request to the generative model carries only one clause? → A: Deterministically: for each mandatory element in the knowledge base, signs (Spanish patterns) are searched across the whole contract text; if none match, the element is reported as a gap with its article reference and flagged for manual review. No external requests are made for this check. (owner's decision, outside the question limit)
- Q: Should the report be stored on the server (revising the earlier answer)? → A: Yes. The report is stored on the server for 30 days from creation and then deleted. The contract text is still not stored and is deleted right after the report is generated. The earlier answer "current session only" is replaced by this. (owner's decision, outside the question limit)

## 2. Users
- **Tenant / buyer (primary):** non-lawyer who wants to understand a contract before signing.
- **Owner / seller:** wants to check their draft is complete and compliant.
- **Reviewer (internal):** inspects low-confidence items the system flags.

## 3. Requirements

### Functional requirements
- Upload a contract (PDF/DOCX). Scanned PDFs are processed via OCR only when the optional OCR fallback is available; otherwise the user gets an actionable error and no partial report (see AC12).
- Split the contract into individual clauses by legal markers.
- Detect contract type: compraventa vs locación.
- Detect the signing date to select the applicable legal regime.
- For each clause: retrieve the applicable norms (national + CABA) from the knowledge base.
- Check the applicable CABA stamp tax (impuesto de sellos), including the vivienda-única exemption and who bears it. For sale contracts the amount is evaluated; for lease contracts the report states only whether the tax applies and who bears it, with no amount; the rate is marked pending until it is confirmed from the Ley Tarifaria 2026.
- The signing date selects the applicable legal regime for both sale and lease contracts, using the validity periods of the norms in the knowledge base (not the current date). One regime applies to the whole contract; clauses are not assigned individual regimes.
- Generate a per-clause explanation: risk level, legal mismatch, with an article reference.
- Check the contract for mandatory elements defined in the knowledge base (e.g., price, term, parties' addresses). The check is deterministic (pattern matching over the whole contract text, no external call). A mandatory element with no match is reported as a gap with its article reference and is flagged for manual review.
- Produce a consolidated report (risks, gaps, non-compliance, and estimated sellos for sale contracts; for lease contracts only the sellos status defined above).
- Store the report for 30 days and let the user retrieve it by its report identifier, in any supported language.
- Render the report in Spanish, English, or Russian.
- Any access to the service from outside the local or pilot environment requires authentication. The authentication method is defined before such access is enabled.

### Key entities
- **Contract**: uploaded document; exists only for the duration of one review.
- **Clause**: a numbered or titled part of the contract, with its text and position.
- **Norm**: a legal provision from the knowledge base, with its article, regime, validity period, and source.
- **Finding**: a risk, gap, or mismatch for a clause, linked to norms or marked as "no applicable norm found".
- **Report**: the consolidated result for one contract; stored for 30 days; contains no contract text.

## 4. Non-functional requirements
- Analysis runs on the **Spanish original** only; translation is an output layer.
- Legal knowledge lives in the **knowledge base of legal norms**, never hard-coded.
- Norms used in the review are restricted to **jurisdiction ∈ {nacional, CABA}**; other provinces are excluded.
- Every finding cites a specific article/norm, selected by the contract's signing date.
- Every translated report carries a disclaimer: only the Spanish original is legally binding.
- Contracts are sensitive data: each request to the external generative-model service carries one clause together with the norms found for it, never the whole contract. External service calls are logged; logs never store contract text. The uploaded contract is deleted right after the report is produced. The contract text is never stored. The report is stored on the server for 30 days from its creation and is then deleted; it contains no contract text beyond clause identifiers and headings. The report is retrievable by its report identifier (an unguessable identifier) for the duration of its retention period.
- Target: for a contract of up to 10 clauses, at least 95% of reviews complete in under 60 seconds.

## 5. User Scenarios & Testing

### Use cases
- UC1: Lease signed in 2026 → system applies the DNU 70/2023 regime.
- UC2: Lease signed in 2022 → system applies the Ley 27.551 regime.
- UC3: Contract missing a mandatory clause → system reports the gap with the governing article.
- UC4: Ambiguous clause → system flags low confidence for manual review.
- UC5: Sale of a vivienda única below the CABA threshold → system reports stamp-tax exemption; above it → reports the rate on the excess.
- UC6: User retrieves a stored report later in another language → system renders it without re-analyzing the contract.

### Edge cases
- A scanned PDF arrives and OCR is unavailable → actionable error, no report.
- No signing date can be found in the text → the user is asked for it before a regime is chosen; a date supplied by the user takes priority over a detected one, and any conflict is noted in the report.
- No clause markers are recognized → actionable error; the whole document is not treated as one clause.
- A clause has no applicable norm in the knowledge base → the finding states that no applicable norm was found and the clause is flagged for manual review.
- The external generative-model service is unavailable → automatic retries, then an actionable error; no partial report.
- A sale contract with no property valuation stated in the text → the stamp-tax amount is not calculated; the report says so.
- A lease stamp-tax rate not yet confirmed → the rate is marked pending.
- A report is requested after its retention period → "not found", the same response as for an unknown identifier.
- Clauses that seem to fall under different regimes → one regime for the whole contract, chosen by signing date.

## 6. Acceptance criteria (EARS)
- **AC1 (Event):** WHEN a user uploads a PDF/DOCX contract, THE system SHALL extract the text and split it into clauses by markers (CLÁUSULA / ARTÍCULO / numbering).
- **AC2 (Ubiquitous):** THE system SHALL perform the norm search and legal reasoning on the Spanish original text.
- **AC3 (Event):** WHEN a contract is ingested, THE system SHALL detect whether it is a compraventa or a locación.
- **AC4 (Unwanted):** IF the signing date is earlier than DNU 70/2023 (Dec 2023), THEN THE system SHALL apply the Ley 27.551 regime to the whole contract (lease or sale), per the signing-date rule in section 3.
- **AC5 (Ubiquitous):** THE system SHALL restrict retrieved norms to jurisdiction ∈ {nacional, CABA} and SHALL NOT apply other provinces' local rules.
- **AC6 (Event):** WHEN reviewing a contract, THE system SHALL evaluate the applicable CABA stamp tax (impuesto de sellos), including the vivienda-única exemption, and SHALL report who bears it.
- **AC7 (Ubiquitous):** THE system SHALL attach a specific article/norm reference to every finding; IF no applicable norm is found in the knowledge base, THEN the finding SHALL state explicitly that no applicable norm was found.
- **AC8 (Optional):** WHERE the user selects English or Russian, THE system SHALL translate the finished report while preserving original Spanish legal terms in parentheses.
- **AC9 (State):** WHILE analysis is in progress, THE system SHALL display a progress indicator.
- **AC10 (Unwanted):** IF the best relevance score of the norms found for a clause is below 0.3, THEN THE system SHALL mark the clause for manual review. The threshold is provisional and is tuned after the first evaluation run.
- **AC11 (Ubiquitous):** THE system SHALL include in every rendered report a disclaimer that (a) only the Spanish original is legally binding, (b) the report is informational, and (c) the final determination is made by a qualified lawyer.
- **AC12 (Unwanted):** IF text extraction fails or the document is unreadable, THEN THE system SHALL return an actionable error and SHALL NOT produce a partial report silently.
- **AC13 (Unwanted):** IF no signing date can be detected, THEN THE system SHALL ask the user for it before selecting a legal regime.
- **AC14 (Unwanted):** IF the external generative-model service is unavailable or returns an error, THEN THE system SHALL retry automatically a limited number of times (the number is set in the plan); IF the failure persists, THEN THE system SHALL return an actionable error and SHALL NOT produce a partial report.
- **AC15 (Event):** WHEN a stored report reaches 30 days after its creation, THE system SHALL delete it; a request for that report identifier SHALL then return "not found", the same response as for an unknown identifier.
- **AC16 (Event):** WHEN a stored report is requested with a language parameter, THE system SHALL render it in that language from the stored language-neutral report, without re-running the analysis or sending anything to the generative-model service for Spanish.
- **AC17 (Event):** WHEN a mandatory element defined in the knowledge base has no matching evidence anywhere in the contract text, THE system SHALL report it as a gap with the governing article reference and SHALL flag it for manual review.

## 7. Out of scope (Phase 0)
- Confidence-gated routing and a trained classifier (Phase 1).
- A fine-tuned Spanish language model (Phase 2).
- Editing or auto-rewriting contract clauses.
- Legal advice or representation — the product is informational only.
- Jurisdictions outside CABA; languages beyond ES/EN/RU.
- User accounts and access control beyond the authentication requirement in section 3.

## 8. Dependencies
- National knowledge base: CCyC (locación arts. 1187–1226; compraventa arts. 1123–1171), DNU 70/2023, Ley 27.551.
- CABA knowledge base: Código Fiscal / Ley Tarifaria CABA (impuesto de sellos), reference contracts.
- External generative-model service for reasoning and translation: a cloud service approved by the project owner for client contract data. The provider is fixed in the plan; its data-retention and training terms are verified before the first real client contract is sent.

## 9. Success Criteria

### Measurable Outcomes
- **SC-001**: For contracts of up to 10 clauses, at least 95% of reviews complete in under 60 seconds.
- **SC-002**: 100% of findings either cite a specific norm or state explicitly that no applicable norm was found.
- **SC-003**: In 100% of test cases, the regime applied matches the regime in force on the signing date, including dates on either side of 30 December 2023.
- **SC-004**: 100% of reports, in every language, carry the disclaimer required by AC11.
- **SC-005**: 100% of failed reviews (unreadable file, unavailable scan support, unavailable external service) return an error and no partial report.
- **SC-006**: 100% of low-confidence clauses and mandatory-element gaps are flagged for manual review.
- **SC-007**: After the 30-day retention period, 0 reports remain retrievable, and an audit of stored data finds no contract text.

## 10. Assumptions
- Contracts are Spanish-language residential sale or lease contracts in CABA; the signing date is stated in the text or supplied by the user.
- Text can be extracted from PDF and DOCX files; scanned documents are processed only when the OCR fallback is available.
- Legal sources in the knowledge base are reviewed against official publications before they are used.
- The lease stamp-tax rate is unknown until it is confirmed; until then it is reported as pending.
- The property's fiscal valuation, needed for the sale stamp-tax base, is taken from the contract text; when it is absent, no amount is calculated.
- Phase 0 runs in a local or pilot environment; external access waits for the authentication method to be defined.
- Users read Spanish, English, or Russian; the Spanish report is the authoritative version.

## 11. Open questions
- Confidence threshold for AC10: provisional value 0.3 (relevance score), tuned after the first evaluation run.
- Reference (model) contracts: not required in phase 0; compared against legal norms only. Added later.
- Contracts with clauses under multiple legal regimes: phase 0 applies one regime per contract, chosen by signing date (deliberate simplification).
- CABA stamp-tax rate for leases (locación): pending until confirmed from the Ley Tarifaria 2026.
- Authentication method for external access (to be defined before external access is enabled).
