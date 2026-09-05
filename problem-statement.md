# Cashe: Financial Ingestion Problem Statement

## The problem

Financial systems capture **what happened**, but the evidence explaining **why it happened** is fragmented across ERPs, banks, payment processors, inboxes, spreadsheets, documents, calls, and hundreds of customer-specific AP portals.

A ledger may show that cash decreased or revenue changed, but it rarely captures:

- When an invoice was submitted
- Whether it was approved, rejected, or disputed
- Why payment was delayed
- Whether a PO or attachment was missing
- Whether a charge is recurring or one-time
- Whether an invoice was corrected
- Which version is authoritative
- What finance knew when it originally closed the period

This operational context often exists only inside portal workflow states, emails, voice conversations, remittance documents, and employees' undocumented procedures.

## Why existing tools are insufficient

AP and customer portals lack a universal interface. Even customers using the same platform, such as Coupa or SAP Ariba, can configure different fields, entities, validation rules, attachments, and approval workflows.

Traditional approaches address only parts of the problem:

- APIs work only for connected and supported systems.
- ETL tools assume structured, accessible data.
- OCR extracts documents only after they arrive.
- Traditional RPA requires brittle portal-specific scripts.
- General browser agents can navigate but cannot prove financial completeness.
- Analysis products operate downstream and assume their inputs are already trustworthy.

None reliably answers:

> Did we acquire every expected financial artifact, from the correct entity and period, with enough evidence to trust and explain it?

As a result, finance teams manually retrieve reports, download invoices, chase missing statements, normalize inconsistent formats, reconcile conflicting versions, and reconstruct business context before analysis can begin.

## Why this is a problem of scale

The complexity is not simply the number of portal brands. It expands across:

```text
Customers
× portal configurations
× legal entities
× workflow types
× authentication states
× reporting periods
× interface changes
```

Each additional customer can introduce another login, submission procedure, field mapping, status vocabulary, and set of exception rules. The resulting process knowledge lives inside employees' memories and must be relearned whenever systems or personnel change.

Failures are frequently silent. An automation may complete while selecting the wrong entity, exporting only one page, using the wrong period, leaving an invoice in draft, or missing a later rejection.

## Cashe's mission

> **Acquire every expected financial artifact and its operational context, prove that the resulting dataset is complete, preserve its history and evidence, route consequential ambiguity to humans, and deliver trusted data ready for financial analysis.**

## Solution concept

### 1. Bounded browser agents

Cashe assigns each browser agent a narrow, verifiable task:

```text
Goal: Retrieve August approved invoices
Allowed system: Customer A's Coupa instance
Permissions: Read-only
Entity: Cashe US
Period: August

Success checks:
- Correct entity and period selected
- Every result page captured
- Portal total reconciles to export total
- Required columns are present
- Artifact is not a duplicate
```

The agent cannot browse outside its assigned system or perform payments and other irreversible actions. It stops and escalates when constraints or verification checks fail.

### 2. SOP learning

A finance employee demonstrates a workflow once. Cashe converts the demonstration into a semantic, reusable SOP instead of fixed coordinates or selectors.

Cashe remembers:

- Successful navigation patterns
- Portal terminology
- Customer-specific requirements
- Field mappings
- Expected reports and delivery cadence
- Verification rules
- Known failure states
- Human corrections

Only verified successes and approved human corrections can update an SOP. Proposed changes remain versioned and reviewable.

### 3. Intelligent acquisition routing

Cashe selects the safest available acquisition method:

1. API or direct integration
2. SFTP, inbox, or shared folder
3. Bounded browser agent
4. Automated email request
5. Voice agent
6. Human-assisted retrieval

Voice and email agents obtain missing artifacts and business context:

> "We have not received August's statement. Can you send it to ingest@cashe.ai?"

Their transcripts, sender identity, commitments, and resulting documents become evidence. Voice statements provide context but do not become authoritative financial facts without corroboration or human approval.

### 4. Completeness monitoring

Cashe maintains a registry of expected source obligations:

```text
AWS invoice                Monthly by Day 2
Stripe settlement report  Daily
Customer A remittance      After each payment
Subsidiary trial balance   Monthly by Day 3
```

This enables Cashe to identify missing data proactively rather than processing only what happens to arrive.

### 5. Conflict detection and human escalation

Cashe detects:

- Duplicate files
- Corrected or reissued invoices
- Conflicting amounts
- Vendor or customer identity ambiguity
- Legal-entity mismatches
- Different transaction statuses
- Missing records
- Late-arriving information
- Period and cutoff conflicts
- Material SOP changes

Routine, verified ingestion proceeds autonomously. Consequential ambiguity is escalated to a human with the conflict, supporting evidence, likely cause, and recommended resolution already assembled.

Human decisions produce:

- A resolved canonical record
- An immutable decision log
- A proposed mapping or SOP update
- A reusable resolution pattern

Conflicting evidence is never silently overwritten.

## Temporal financial data

Cashe uses an append-only, bitemporal model. Every assertion tracks:

- **Effective time:** When the financial event applies
- **Observed time:** When Cashe learned about it

Example:

```text
Invoice INV-1042
Effective date: August 31

Version 1: $1,000 — observed September 2
Version 2: $1,200 — observed September 8
Version 2 supersedes Version 1
```

This allows Cashe to answer both:

- "What is the latest known amount?" → $1,200
- "What did finance know when it closed on September 5?" → $1,000

The current view uses the latest authoritative version, while previous versions remain available for historical analysis, audit, and as-of-close reporting.

## Analysis enabled by better ingestion

Portal and communication evidence transforms shallow explanations:

> Cash decreased because customers paid late.

Into evidence-backed explanations:

> Cash decreased $620K because three enterprise invoices remained in procurement review. Two were submitted nine days late due to missing POs; one was rejected twice for an incorrect legal entity.

It can also correct false interpretations:

> The $180K revenue reduction was not churn. The customer requested that implementation billing move to October after a deployment delay, confirmed through email and approved by finance.

Cashe enables analysis of:

- Price, volume, mix, FX, and timing
- Revenue quality and customer concentration
- Invoice approval and rejection bottlenecks
- Collectability and cash-flow risk
- Unrecorded liabilities
- Missing credits
- Contract and pricing leakage
- Revision history
- Accrual accuracy
- Operational causes behind financial outcomes

## Product loop

```text
Discover expected source
→ Learn retrieval SOP
→ Acquire artifact and context
→ Verify completeness
→ Normalize without destroying history
→ Detect conflicts
→ Escalate ambiguity with evidence
→ Learn from approved resolutions
→ Produce trusted, analysis-ready data
```

## Differentiated pitch

> **Cashe is a self-improving financial evidence layer that learns how to retrieve data and operational context across fragmented systems, proves that nothing material is missing, preserves exactly what finance knew at every point in time, and enables explanations grounded in the events behind the ledger.**
