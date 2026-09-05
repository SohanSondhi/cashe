# Cashe MVP Technical Specification

## 1. Purpose

Cashe demonstrates that richer financial explanations begin with better ingestion.

The MVP starts from a hard-coded corporate bank statement as the source of truth for settled cash. An LLM orchestrator investigates material cash changes by acquiring operational evidence from several realistic local source systems built specifically for the demo:

- A mock MCP accounting server
- A mock REST API
- A mock customer AP browser portal
- A mock voice counterparty

The orchestrator uses Tavily to research which machine-access methods a source product normally supports, combines that research with the customer's configured access, and chooses an acquisition method using this preference policy:

```text
MCP → API → bounded browser agent → voice agent
```

This preference is guidance for the LLM, not a hard-coded `if/else` router or a stop-after-first-success rule. The orchestrator can ask multiple specialized subagents to investigate the same fact when more evidence is useful. The runtime provides only narrow, read-only tools and preserves the evidence returned by each source.

## 2. Product statement

> Cashe is a self-improving financial evidence layer that starts from an authoritative financial result, retrieves the operational context needed to explain it, and escalates unresolved conflicts to humans with the relevant evidence already assembled.

## 3. MVP outcome

Given August and September bank statements, Cashe must produce this conclusion:

> September cash decreased by $620,000. Three expected enterprise receipts totaling $620,000 did not settle by month-end. NovaWorks' $240,000 invoice was submitted nine days late after a missing PO blocked submission. BluePeak's $210,000 invoice was rejected twice because the wrong legal entity was selected. HarborLine's $170,000 invoice remained in procurement review after its PO arrived late, according to a voice confirmation that still requires documentary corroboration.

The explanation must cite the source assertion or artifact supporting every material claim and distinguish verified facts from contextual or unresolved claims. Before the final explanation is accepted, a human must resolve the BluePeak legal-entity conflict between the accounting record and the customer portal.

## 4. Scope

### In scope

- Two realistic, synthetic USD bank statements
- One LLM orchestrator with tool calling
- Tavily-backed capability research
- Local mock MCP, REST API, browser portal, and voice systems
- Source registry and access entitlements
- Evidence capture and immutable raw artifacts
- Browser-only SOP storage and run history
- Human escalation for conflicts and low-authority evidence
- Append-only temporal assertions
- A current view and an as-of view
- One evidence-backed cash-variance explanation
- A minimal operator UI for running and reviewing the investigation

### Non-goals

- Connecting to real banks, ERPs, Coupa, or SAP Ariba
- Initiating payments or modifying financial systems
- Production credential management
- General-purpose autonomous browsing
- Real telephony unless time and credentials permit
- Full double-entry accounting
- Production-grade entity resolution
- Claiming causal certainty from uncorroborated communications
- Building a universal integration platform during the hackathon

## 5. Design principles

### 5.1 Financial spine first

The bank statement is authoritative only for settled cash:

- Opening and closing booked balances
- Credits and debits that settled
- Booking and value dates
- Bank and customer references

The bank does not determine the accounting meaning of a transaction. ERP, invoice, portal, remittance, contract, and human evidence enrich that cash movement.

### 5.2 LLM-directed investigation

The main orchestrator creates specialized subagents for research and evidence gathering. It decides:

- What information is missing
- Which research and acquisition subagents to create
- Which sources should be investigated in parallel
- Whether a first result is sufficient or needs corroboration
- Whether the evidence explains the variance
- Whether every reasonable evidence path has been exhausted

The runtime remains deliberately small:

- Subagents receive only the source tools relevant to their assignment.
- Source access is read-only.
- Every returned artifact and assertion retains its provenance.
- Browser agents are restricted to their assigned portal.

### 5.3 Assertions, not overwrites

Every source contributes an assertion. Conflicting assertions coexist until a policy or human resolution establishes the canonical interpretation.

### 5.4 Human adjudication follows evidence exhaustion

Cashe does not ask a human to investigate a conflict that its subagents can still investigate. When sources disagree, the orchestrator expands the investigation across every available and authorized evidence source that could resolve the disagreement.

For example:

```text
ERP:   Invoice belongs to Cashe Software, Inc.
API:   Invoice belongs to Cashe Holdings LLC.
Voice: AP representative says Cashe Software, Inc.
Email: No confirming document found.
```

Only after Cashe gathers and summarizes the available evidence does it ask a human:

> Which assertion should govern, and why?

The human receives the conflicting assertions, source links, timestamps, likely interpretation, and remaining uncertainty. The resolution becomes new evidence for future investigations.

Cashe may stop earlier only when access is forbidden or the requested action is outside the read-only scope; that is a refusal, not a human adjudication request.

### 5.5 SOP learning belongs only to browser agents

MCP, API, Tavily, and voice subagents do not use SOPs. They operate through their own tool contracts and return evidence.

Only a browser subagent learns a semantic SOP from successful portal navigation. It may propose an SOP update after a completed run. Successful paths and human-corrected browser paths can inform later browser runs; failed paths do not become preferred procedures.

## 6. Demo scenario

All companies, accounts, people, and transactions are fictional.

### 6.1 Cashe company

```text
Legal entity: Cashe Software, Inc.
Entity code: CASH-US
Bank: Northstar Commercial Bank
Account: Operating ••1842
Currency: USD
```

### 6.2 Bank statements

The synthetic statement schema follows common BAI2 and ISO 20022 camt.053 concepts:

```text
statement_id
account_id
account_owner
currency
period_start
period_end
opening_booked_balance
closing_booked_balance
generated_at

transaction_id
credit_debit_indicator
amount
booking_date
value_date
bank_transaction_code
bank_reference
customer_reference
counterparty_name
remittance_information
```

Amounts are stored as positive integer cents. Direction is represented separately as `CRDT` or `DBIT`.

#### August

```text
Opening booked balance:  $2,900,000
Total credits:            $2,850,000
Total debits:             $2,550,000
Closing booked balance:   $3,200,000
```

#### September

```text
Opening booked balance:  $3,200,000
Total credits:            $2,230,000
Total debits:             $2,850,000
Closing booked balance:   $2,580,000
Net cash change:           -$620,000
```

Required invariant:

```text
opening balance + credits - debits = closing balance
```

### 6.3 Expected unsettled receipts

The mock accounting MCP server reports three material open invoices:

```text
INV-NW-1042  NovaWorks Group  $240,000  Due September 20
INV-BP-2088  BluePeak Labs    $210,000  Due September 22
INV-HL-3301  HarborLine Co.   $170,000  Due September 25
                                          ----------
Total                                      $620,000
```

### 6.4 Operational evidence

#### NovaWorks: REST API

- Customer system: ProcureFlow
- Configured access: API token
- Invoice status: `PENDING_APPROVAL`
- First attempted submission: September 1
- Successful submission: September 10
- Delay: Nine days
- Reason: Required PO was unavailable
- Evidence authority: High

#### BluePeak: browser-only portal

- Customer system: BluePeak Vendor Center
- Configured access: Read-only portal identity
- No usable customer API entitlement
- Invoice status: `DISPUTED`
- Rejection count: Two
- Reason: Invoice submitted under `Cashe Holdings LLC` instead of `Cashe Software, Inc.`
- Accounting MCP assertion: Legal entity is `Cashe Software, Inc.`
- Portal assertion: Submitted legal entity is `Cashe Holdings LLC`
- Required control: Open a legal-entity conflict and obtain human resolution
- Approved interpretation for the demo: The accounting entity is correct and the portal value represents the customer-side submission error
- Evidence authority: High after browser verification

#### HarborLine: voice

- No MCP or API
- Browser portal unavailable in the simulated incident
- Voice contact: HarborLine AP service desk
- Claimed status: Procurement review
- Claimed reason: PO arrived after the original invoice
- Promised follow-up: Email confirmation within one business day
- Evidence authority: Low until corroborated
- Required action: Human review or wait for documentary confirmation

## 7. System architecture

```text
Operator UI
    │
    ▼
FastAPI application
    │
    ├── LLM Orchestrator
    │     ├── Research subagent
    │     │     └── Tavily + source registry
    │     ├── MCP acquisition subagent
    │     ├── API acquisition subagent
    │     ├── Browser acquisition subagent
    │     │     └── Browser-only SOP memory
    │     ├── Voice acquisition subagent
    │     └── Evidence synthesis subagent
    │           └── Human adjudication packet
    │
    ├── SQLite evidence and temporal store
    │
    └── Cursor-built local source mocks
          ├── Accounting MCP server
          ├── ProcureFlow REST API
          ├── BluePeak browser portal
          └── HarborLine voice simulator
```

### Recommended MVP stack

- Python 3.12+
- FastAPI
- Pydantic
- SQLite with SQLAlchemy or SQLModel
- OpenAI-compatible tool-calling client with configurable model
- Tavily Python client
- FastMCP for the local MCP server
- Playwright plus an LLM browser loop
- Server-rendered HTML or minimal vanilla JavaScript UI
- Pytest

The MVP should avoid a separate frontend build pipeline unless implementation time remains.

### Specialized subagents

The orchestrator creates subagents dynamically around missing facts rather than maintaining a fixed workflow graph.

- **Research subagent:** Uses Tavily and the source registry to identify possible access methods and relevant product behavior.
- **MCP subagent:** Queries an authorized MCP server and returns source assertions.
- **API subagent:** Investigates an authorized REST source and returns source assertions.
- **Browser subagent:** Navigates one allowlisted portal, uses or improves that portal's SOP, and captures the visible workflow state.
- **Voice subagent:** Contacts a configured counterparty for missing context or documentary follow-up.
- **Evidence synthesis subagent:** Compares all gathered assertions, identifies agreement and conflict, and prepares either the explanation or a human adjudication packet.

Subagents do not decide which assertion is the universal source of truth. They gather and characterize evidence for the orchestrator.

## 8. Capability discovery

### 8.1 Important boundary

Tavily cannot discover local mock endpoints from the public web. It provides external product-capability research; Cashe's source registry describes what access this specific customer actually possesses.

The orchestrator combines:

1. Tavily findings, such as whether a platform generally supports APIs, cXML, SFTP, or a supplier portal.
2. Local entitlements, such as whether Cashe has an API token or only portal credentials.
3. Previous successful acquisition runs.
4. The preferred acquisition policy.

General platform capability does not imply customer authorization. Tavily results may inform routing, but they cannot create financial assertions or authorize access to a source.

### 8.2 Reproducibility

- Cache the Tavily response and citations as a raw artifact.
- Support live Tavily search when `TAVILY_API_KEY` is present.
- Fall back to a committed cached response for the demo.
- Record whether a capability decision used live or cached research.

### 8.3 Source registry example

```json
{
  "source_id": "bluepeak-vendor-center",
  "organization": "BluePeak Labs",
  "product_family": "custom_ap_portal",
  "base_url": "http://localhost:8000/mock/bluepeak",
  "allowed_hosts": ["localhost"],
  "entitlements": {
    "mcp": false,
    "api": false,
    "browser": true,
    "voice": true
  },
  "credential_ref": "mock://bluepeak/read-only",
  "permission": "read_only",
  "expected_artifacts": ["invoice_status", "dispute_reason"],
  "preferred_sop_id": "sop-bluepeak-status-v1"
}
```

## 9. Orchestrator behavior

### 9.1 System policy

The main agent receives these instructions:

```text
You investigate material changes in authoritative financial records.

For each missing fact:
1. Create a research subagent when source capabilities are unknown.
2. Prefer MCP, then API, then bounded browser, then voice for the first inquiry.
3. Create additional specialized acquisition subagents when corroboration or
   conflict resolution requires more than one source.
4. Treat the bank as authoritative for settled cash, not transaction meaning.
5. Preserve every source assertion and never hide disagreement.
6. When sources conflict, exhaust every reasonable authorized evidence path
   before creating a human adjudication packet.
7. Give the human the ERP, API, browser, voice, and document evidence together,
   plus your likely interpretation and what remains uncertain.
8. Cite evidence IDs in the final explanation.
9. Do not claim causation beyond the available evidence.
10. Use SOP memory only when delegating work to a browser subagent.
```

There is no code branch that selects a source method or determines which source wins. The LLM orchestrator creates subagents, reviews their evidence, and decides what to investigate next. The host application exposes only the source access configured for the demo.

### 9.2 Investigation loop

1. Load and validate the August and September bank statements.
2. Identify the material September cash decrease.
3. Ask what expected receipts did not settle.
4. Create an MCP subagent to retrieve open receivables.
5. Create research subagents for each customer whose access methods are unknown.
6. Create API, browser, or voice subagents according to the available access and the evidence still needed.
7. Store every returned artifact and source assertion.
8. Ask the evidence synthesis subagent to compare the assertions.
9. If a conflict exists, create further acquisition subagents for every remaining source that could resolve it.
10. After evidence is exhausted, present the BluePeak entity conflict and HarborLine's uncorroborated voice claim to a human together with the complete evidence packet.
11. Store the human decisions as additional assertions.
12. Reconcile the three expected receipts to the $620,000 variance.
13. Generate an explanation with claim-level citations and confidence.

## 10. Tool contracts

### `load_bank_statement`

Input:

```json
{"period": "2026-09"}
```

Output includes the statement, transactions, artifact ID, and reconciliation result.

### `research_source_capabilities`

Input:

```json
{
  "source_name": "ProcureFlow",
  "required_fact": "invoice status and rejection history"
}
```

Output includes Tavily summary, URLs, retrieval time, cache status, and candidate methods. Research is advisory.

### `query_accounting_mcp`

Input:

```json
{
  "tool": "list_open_invoices",
  "arguments": {
    "entity": "CASH-US",
    "as_of": "2026-09-30",
    "minimum_amount_cents": 10000000
  }
}
```

### `query_source_api`

Input:

```json
{
  "source_id": "novaworks-procureflow",
  "operation": "get_invoice_timeline",
  "parameters": {"invoice_number": "INV-NW-1042"}
}
```

The tool permits only registered read operations.

### `run_bounded_browser`

Input:

```json
{
  "source_id": "bluepeak-vendor-center",
  "goal": "Retrieve status and dispute history for INV-BP-2088",
  "sop_id": "sop-bluepeak-status-v1",
  "step_budget": 20,
  "required_checks": [
    "invoice_number_matches",
    "customer_matches",
    "timeline_exhausted"
  ]
}
```

Output includes extracted assertions, screenshots, action trace, checks, and a proposed SOP patch.

### `place_voice_call`

Input:

```json
{
  "source_id": "harborline-ap-desk",
  "objective": "Determine the status of INV-HL-3301 and request written confirmation",
  "allowed_questions": [
    "invoice status",
    "blocking reason",
    "expected next action",
    "written confirmation request"
  ],
  "turn_budget": 8
}
```

Output includes transcript, speaker identity claim, extracted assertions, promised follow-up, and low-authority classification.

### `create_escalation`

Input:

```json
{
  "title": "HarborLine status lacks documentary evidence",
  "assertion_ids": ["ast-hl-status-1"],
  "recommended_action": "Wait for promised email or approve provisional use",
  "materiality_cents": 17000000
}
```

### `synthesize_explanation`

Input is a structured explanation containing the headline, drivers, confidence labels, assertion IDs, open conflicts, and unknowns.

The evidence synthesis subagent uses the gathered assertions and human decisions to create the explanation. Each material claim carries its supporting assertion IDs, and unresolved disagreement remains visible instead of being narrated away.

## 11. Mock source specifications

### 11.1 Accounting MCP server

Tools:

- `list_open_invoices`
- `get_invoice`
- `get_customer`
- `get_expected_receipts`

The server returns typed JSON and evidence identifiers. It represents an ERP/subledger with a first-class MCP interface.

### 11.2 ProcureFlow REST API

Endpoints:

```text
GET /mock/procureflow/api/v1/invoices/{invoice_number}
GET /mock/procureflow/api/v1/invoices/{invoice_number}/timeline
GET /mock/procureflow/api/v1/remittances
```

Authentication uses a synthetic bearer token. Responses model realistic statuses such as `PENDING_APPROVAL`, `APPROVED`, `DISPUTED`, and `PAID`.

### 11.3 BluePeak Vendor Center

Pages:

```text
/mock/bluepeak/login
/mock/bluepeak/dashboard
/mock/bluepeak/invoices
/mock/bluepeak/invoices/{invoice_number}
```

The invoice detail page exposes:

- Invoice number
- PO number
- Amount and currency
- Legal entity
- Current status
- Dispute reason
- Status timeline
- Customer comments

The portal intentionally exposes no application API. A demo toggle changes labels and layout while preserving meaning, allowing Cashe to show semantic SOP reuse:

```text
Invoices → Billing Documents
Disputed → Needs Attention
```

The browser agent must recover without using a newly hard-coded selector.

### 11.4 HarborLine voice simulator

The simulator behaves like an AP service desk and supports multi-turn text dialogue through a voice-shaped tool contract. It returns transcript events with synthetic timestamps.

The mock respondent knows:

- Invoice `INV-HL-3301`
- Current procurement-review state
- Missing PO history
- No confirmed payment date
- Ability to promise an email but not generate authoritative documentation

The MVP need not synthesize audio. If time permits, text-to-speech and speech-to-text can wrap the same contract without changing the orchestrator.

## 12. SOP model

```json
{
  "sop_id": "sop-bluepeak-status-v1",
  "source_id": "bluepeak-vendor-center",
  "goal_type": "retrieve_invoice_status",
  "version": 1,
  "status": "approved",
  "parameters": ["invoice_number"],
  "steps": [
    {"intent": "authenticate with the registered read-only identity"},
    {"intent": "open the invoice or billing document collection"},
    {"intent": "find the invoice matching the supplied invoice number"},
    {"intent": "capture status, dispute reason, and complete timeline"}
  ],
  "verification": [
    "invoice_number_matches",
    "amount_matches_accounting_record",
    "timeline_exhausted"
  ],
  "learned_hints": [
    "The invoice collection may be labeled Invoices or Billing Documents"
  ],
  "created_from_run_id": "run-demo-001"
}
```

SOP changes are append-only:

- `draft`: proposed by an agent
- `approved`: human-approved or promoted after fully verified success
- `deprecated`: retained but excluded from default retrieval

The demo should show fewer exploratory browser actions on the second successful run.

## 13. Data model

### `source_registry`

Describes the system, organization, access entitlements, permission level, and expected artifacts.

### `source_obligation`

Describes what Cashe expects to retrieve, from where, for which entity, and by what cadence.

### `raw_artifact`

Immutable source material:

```text
id, source_id, media_type, content_hash, storage_path,
retrieved_at, retrieval_method, run_id
```

### `source_assertion`

An individual claim from one artifact:

```text
id, artifact_id, subject_type, subject_id, field, value,
valid_from, valid_to, observed_at, superseded_at,
authority, confidence, status
```

### `financial_event`

Canonical event linked to assertions:

```text
id, event_type, entity_id, amount_cents, currency,
transaction_date, posting_date, financial_period
```

### `evidence_link`

Links a financial event or explanation claim to an artifact, assertion, screenshot, transcript segment, or human decision.

### `sop` and `sop_run`

Store browser-only semantic procedures, portal action traces, observed outcomes, and proposed browser-navigation updates.

### `conflict` and `human_resolution`

Store competing assertion IDs, materiality, recommended disposition, reviewer choice, rationale, and effective time.

## 14. Temporal semantics

Cashe uses append-only bitemporal assertions:

- `valid_from` and `valid_to`: when the claim applies economically
- `observed_at` and `superseded_at`: when Cashe knew or stopped relying on it

The database must support:

```text
Current view:
What is the latest accepted explanation?

As-of view:
What did Cashe know at the September 30 close?
```

Corrections create new assertions that reference prior assertions. They do not mutate or delete history.

## 15. Evidence and confidence

Suggested authority levels:

```text
SETTLEMENT       Bank statement
BOOKS            ERP or accounting MCP
WORKFLOW         Authenticated portal/API state
DOCUMENT         Invoice, PO, remittance, contract
COMMUNICATION    Email or voice statement
HUMAN_RESOLUTION Approved reviewer decision
```

Authority is scoped to the fact. A bank is authoritative for settlement but not invoice meaning. A portal is authoritative for its own workflow state but not bank settlement.

Final explanations label claims:

- `verified`: supported by authoritative evidence and passed checks
- `corroborated`: supported by multiple compatible sources
- `provisional`: plausible but awaiting required evidence
- `conflicted`: material sources disagree

## 16. Human escalation packet

The evidence synthesis subagent creates this packet only after the orchestrator has tried every reasonable, authorized source that could resolve the conflict. The review UI must show:

- The disputed or provisional claim
- Amount and materiality
- Competing assertions
- Source authority and timestamps
- Evidence sources attempted, unavailable, and still missing
- Direct artifact, screenshot, or transcript links
- The orchestrator's likely explanation
- Recommended next action

Available decisions:

```text
Approve provisionally
Choose an assertion
Request more evidence
Correct the entity mapping
Reject the proposed interpretation
```

The resolution becomes a new immutable assertion and may update a canonical mapping. Only a correction to browser navigation can produce a draft browser SOP update.

## 17. Minimal application interface

### Operator pages

```text
/                         Investigation dashboard
/investigations/{id}      Live tool and evidence timeline
/sources                   Source registry and method availability
/sops                      SOP versions and run performance
/escalations               Human review queue
/evidence/{id}             Raw artifact or evidence detail
```

### Application endpoints

```text
POST /api/investigations
GET  /api/investigations/{id}
GET  /api/investigations/{id}/events
GET  /api/explanations/{id}
GET  /api/escalations
POST /api/escalations/{id}/resolve
POST /api/mock/bluepeak/layout-mode
```

The investigation page should stream or poll orchestrator events so the demo visibly shows Tavily research, method selection, evidence acquisition, and escalation.

## 18. Operating boundaries

- All browser hosts must be allowlisted.
- All source operations must be read-only.
- Credentials are referenced by opaque IDs and never placed in prompts, traces, screenshots, or transcripts.
- Voice claims remain provisional until corroborated or accepted by a human.
- Source disagreements remain visible until a human adjudicates them.
- Every material explanation claim retains links to its evidence.
- The orchestrator must state uncertainty rather than fabricate missing context.

## 19. Acceptance criteria

### Financial correctness

- Both bank statements satisfy the balance invariant.
- The September net cash change is exactly negative $620,000.
- The three open invoices sum to exactly $620,000.

### Agentic routing

- The orchestrator dynamically creates research and acquisition subagents without a hard-coded router.
- An MCP subagent gathers the open receivables.
- An API subagent gathers NovaWorks evidence after capability and entitlement evaluation.
- A browser subagent gathers BluePeak evidence because no authorized MCP/API exists.
- A voice subagent gathers HarborLine evidence after higher-preference methods are unavailable.
- Every method choice includes a recorded reason.

### Browser boundaries and learning

- The browser cannot leave the allowlisted mock portal.
- It performs no mutating business action.
- It extracts the correct BluePeak status, legal entity, and rejection history.
- It passes the required verification checks.
- A second run can use an approved SOP.
- The changed-layout demo either succeeds semantically or escalates safely.

### Evidence and conflicts

- Every raw response, browser trace, screenshot, and voice transcript receives an artifact ID and hash.
- Voice-derived HarborLine status is marked provisional.
- Before asking a human, the orchestrator records every available evidence source it attempted.
- A human escalation contains all gathered assertions, the relevant transcript, the likely interpretation, remaining uncertainty, and a recommended action.
- The BluePeak entity mismatch creates a conflict containing both source assertions.
- Human resolution preserves `Cashe Software, Inc.` as the accounting entity and classifies `Cashe Holdings LLC` as the customer-side submission error.
- Conflicting assertions are preserved rather than overwritten.

### Temporal behavior

- The current endpoint returns the latest accepted assertion.
- An as-of query reproduces the assertions available at a selected close timestamp.

### Final explanation

- It reconciles the three drivers to $620,000.
- It cites evidence for every amount, status, delay, and reason.
- It distinguishes verified portal/API facts from provisional voice context.
- It does not describe a missing receipt as settled cash.
- It cannot use Tavily research as financial evidence.
- It cannot present an unresolved conflict as settled fact.

## 20. Implementation milestones

### Milestone 1: Financial spine and data store

- Create project skeleton and configuration.
- Add two bank statement fixtures.
- Implement balance validation.
- Add SQLite temporal and evidence schema.
- Render the statement comparison.

### Milestone 2: Local source mocks

- Implement the accounting MCP server.
- Implement the ProcureFlow REST API.
- Implement the BluePeak browser portal.
- Implement the HarborLine voice simulator.
- Add realistic fixture data and source registry entries.

### Milestone 3: Orchestrator and tools

- Configure the LLM orchestrator and specialized subagent loop.
- Add Tavily live/cached capability research.
- Add MCP, API, browser, voice, evidence, and escalation tools.
- Restrict each subagent to its relevant read-only source tools.

### Milestone 4: Browser SOP learning and conflict review

- Store browser semantic SOPs and portal run traces.
- Generate proposed browser SOP patches.
- Add promotion and deprecation states.
- Build evidence-exhaustion tracking, the human adjudication packet, and the resolution endpoint.

### Milestone 5: Explanation and demo polish

- Generate claim-level evidence citations.
- Add current and as-of views.
- Add the browser layout-change toggle.
- Add tests for financial invariants, routing outcomes, and safety.
- Script the final two-minute demonstration.

## 21. Demo script

1. Show August and September bank statements and the verified $620,000 cash decline.
2. Ask Cashe: “Why did cash decrease in September?”
3. Watch the orchestrator create an MCP subagent that identifies three expected receipts.
4. Show Tavily capability research and the customer's actual entitlements.
5. Observe API acquisition for NovaWorks.
6. Observe bounded browser acquisition for BluePeak.
7. Observe voice fallback for HarborLine.
8. Show the orchestrator exhausting the remaining sources for the BluePeak and HarborLine uncertainties.
9. Resolve the BluePeak legal-entity conflict from the complete evidence packet.
10. Review the HarborLine provisional-evidence packet.
11. Show the evidence-linked final explanation.
12. Switch the BluePeak portal layout and rerun to demonstrate semantic SOP reuse.
13. Show the as-of view to prove that later evidence does not erase what finance knew at close.

## 22. Risks and mitigations

### LLM routing may be inconsistent

Mitigation: explicit preference policy, typed tools, limited tool inventory, method-choice logging, and golden-path evaluation fixtures.

### Tavily results may be unavailable or nondeterministic

Mitigation: store live results as artifacts and commit a cited cache for the demo.

### Browser automation may fail during the demo

Mitigation: local controlled portal, approved SOP, bounded step budget, visible fallback, and a recorded successful trace.

### The mock voice channel may feel artificial

Mitigation: model a realistic AP service-desk conversation, preserve authority limits, and optionally add audio without changing the contract.

### The orchestrator may overstate causality

Mitigation: claim-level evidence, authority labels, reconciliation requirements, and explicit provisional/conflicted states.

### “Source of truth” may be misunderstood

Mitigation: consistently state that the bank is authoritative for settlement, the accounting system for recorded books, and operational systems for their own workflow state.

## 23. Research references

- [BAI2 implementation specifications](https://www.svb.com/globalassets/uk-site/products/cash-management/bai2-ir-specs.pdf)
- [Bank of America ISO 20022 camt.053 reference](https://images.em.bankofamerica.com/GTS/ISO_20022/ReferenceGuideBanktoCustomerStatement%28CAMT.053%29.pdf)
- [Coupa: View and manage invoices](https://compass.coupa.com/en-us/products/product-documentation/supplier-resources/for-suppliers/coupa-supplier-portal/set-up-the-csp/invoices/view-and-manage-invoices)
- [Coupa Supplier Portal invoice FAQ](https://docs.coupa.com/en/supplier-documentation/coupa-for-suppliers/the-coupa-supplier-portal-or-csp/features-and-processes-in-the-coupa-supplier-portal/invoices/invoices-faq)

