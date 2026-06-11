# Feature Specification: EOL Trait Query Service

**Feature Branch**: `001-eol-trait-query`

**Created**: 2026-06-11

**Status**: Draft

**Input**: User description: "A service that lets a user ask a biodiversity question in natural language and receive correct, sourced answers drawn from the Encyclopedia of Life (EOL) trait database. The user never writes a query and never sees the underlying query language; they ask, and the system answers or explains why it cannot."

## Clarifications

### Session 2026-06-11

- Q: Target accuracy on the held-out canonical-shape set (US-1–US-5)? → A: 90%
- Q: Fraction of the labeled ambiguity set that must yield a clarification prompt rather than a
  silent wrong answer? → A: 100% (hard gate)
- Q: End-to-end latency target for canonical-shape answers? → A: p95 ≤ 5 seconds (excludes US-7
  novel composition)
- Q: How are upstream EOL failures (timeout/error) handled, distinct from empty results? → A:
  Return an explicit "upstream unavailable" outcome, distinct from "no records found" and from
  internal errors; no tight retry loop (at most a small bounded retry with backoff)
- Q: Disambiguation interaction model — stateful multi-turn or stateless single-shot? → A:
  Stateless single-shot; the service returns structured candidates and the client resubmits with
  the chosen identifier

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Single fact about a taxon (US-1) (Priority: P1)

A user asks a natural-language question about a single measurable attribute of one organism
(e.g., "how heavy is a sea otter?") and receives the recorded measurement(s) with units and
source — or a clear statement that no such record exists.

**Why this priority**: This is the simplest end-to-end path that delivers the core promise —
ask in plain language, get a correct, sourced fact. It exercises taxon resolution, predicate
resolution, quantitative value handling, and provenance, making it the natural MVP.

**Independent Test**: Ask "how heavy is a sea otter?" and confirm the returned body-mass
measurement(s), units, and source match a hand-written query against EOL; confirm a taxon with
no recorded mass returns an explicit "no record" answer.

**Acceptance Scenarios**:

1. **Given** a taxon with recorded body-mass traits, **When** the user asks how heavy it is,
   **Then** the system returns each measurement with units and provenance.
2. **Given** a taxon EOL describes but with no body-mass record, **When** the user asks how
   heavy it is, **Then** the system states clearly that EOL has no such record (not an error).

---

### User Story 6 - Disambiguation (US-6) (Priority: P1)

When the user's term is ambiguous — a common name mapping to multiple taxa, or an attribute
phrase with no confident predicate match — the system asks the user to choose among candidates
instead of guessing.

**Why this priority**: Guessing produces confident-but-wrong answers, which is the worst
failure for a sourced-answer service. Confident resolution (or an explicit choice prompt) is a
prerequisite for trusting every other story, so it ships in the MVP alongside US-1.

**Independent Test**: Ask a question using a common name known to map to multiple taxa and
confirm the system returns a candidate list to choose from rather than a single guessed answer.

**Acceptance Scenarios**:

1. **Given** a common name that resolves to multiple distinct taxa, **When** the user asks
   about it, **Then** the system presents the candidate taxa and requests a choice.
2. **Given** an attribute phrase that matches no controlled predicate with sufficient
   confidence, **When** the user asks, **Then** the system asks the user to clarify the
   attribute rather than answering from an unverified term.

---

### User Story 8 - No data (US-8) (Priority: P1)

For a valid, well-formed question that EOL simply has no records for, the system returns an
explicit "no records found" answer — never an error and never a retry loop.

**Why this priority**: Distinguishing "the question was understood and the answer is empty"
from "something went wrong" is fundamental to a trustworthy answer service and is cheap to get
right early. It guards every other story against masking real coverage gaps as failures.

**Independent Test**: Pose a correctly-resolved question whose upstream result set is known to
be empty and confirm the response is an explicit "no records found", returned once, with no
error surfaced and no retry.

**Acceptance Scenarios**:

1. **Given** a fully resolved question with an empty upstream result, **When** processed,
   **Then** the system returns an explicit "no records found" outcome distinct from an error.
2. **Given** an empty upstream result, **When** processed, **Then** the system does not retry
   the request in a loop.

---

### User Story 2 - Categorical attribute (US-2) (Priority: P2)

A user asks about a categorical attribute (e.g., "what habitat does the raccoon live in?") and
receives the categorical value(s) and their provenance.

**Why this priority**: Extends coverage from quantitative to categorical answers — a distinct
value shape — broadening usefulness once the MVP fact path works.

**Independent Test**: Ask "what habitat does the raccoon live in?" and confirm the returned
categorical habitat term(s) and provenance match a hand-written query.

**Acceptance Scenarios**:

1. **Given** a taxon with recorded categorical habitat traits, **When** the user asks where it
   lives, **Then** the system returns the categorical value(s) with provenance.
2. **Given** a categorical predicate, **When** answered, **Then** the value is presented as a
   controlled term, not as a measurement.

---

### User Story 3 - Ecological association (US-3) (Priority: P2)

A user asks about an interaction between organisms (e.g., "what do sea otters eat?") and
receives the partner taxa in the correct direction (eater vs. eaten) with provenance.

**Why this priority**: Adds taxon-valued, directional answers — a third value shape — and the
direction-correctness requirement makes it a meaningful capability step beyond single-taxon
attributes.

**Independent Test**: Ask "what do sea otters eat?" and confirm the returned partner taxa are
the prey (not the predators) and carry provenance, verified against a hand-written query.

**Acceptance Scenarios**:

1. **Given** a taxon with recorded "eats" associations, **When** the user asks what it eats,
   **Then** the system returns the partner (eaten) taxa with provenance.
2. **Given** a directional interaction, **When** answered, **Then** the relationship direction
   is preserved and never inverted.

---

### User Story 4 - Aggregate / count (US-4) (Priority: P3)

A user asks a counting question (e.g., "how many taxa have a recorded body size?") and receives
a count that correctly rolls up sub-types of the attribute (wingspan, body mass, etc.).

**Why this priority**: Introduces aggregation and attribute roll-up over the established value
shapes; valuable but builds on resolution and predicate-hierarchy handling from earlier stories.

**Independent Test**: Ask "how many taxa have a recorded body size?" and confirm the count
includes taxa recorded under sub-types of size, matching a hand-written roll-up query.

**Acceptance Scenarios**:

1. **Given** an attribute with recorded sub-types, **When** the user asks a count over the
   general category, **Then** the count includes records filed under the sub-types.
2. **Given** a count question, **When** answered, **Then** the system returns a single rolled-up
   number rather than a per-sub-type breakdown unless asked.

---

### User Story 5 - Lineage (US-5) (Priority: P3)

A user asks for the ancestry of a taxon and receives its lineage from the taxon up its parent
chain.

**Why this priority**: A distinct traversal shape (hierarchy walk) that rounds out the canonical
query set; independent of the attribute/association paths.

**Independent Test**: Ask for the ancestry of a known taxon and confirm the returned lineage
matches the taxon's parent chain in EOL.

**Acceptance Scenarios**:

1. **Given** a resolvable taxon, **When** the user asks for its ancestry, **Then** the system
   returns the ordered lineage from the taxon up to the root of its parent chain.

---

### User Story 7 - Novel multi-step question (US-7) (Priority: P3)

A user asks a compositional question that combines relationships the system does not pre-model
(e.g., "which pollinators visit plants that humans use?"). The system either answers it by
composing steps or clearly states the question is outside current capability — but never returns
a plausible-looking wrong answer.

**Why this priority**: Handles the long tail beyond the canonical shapes. It is lower priority
because the canonical shapes deliver most value first, but the "never confidently wrong" promise
must hold here too.

**Independent Test**: Pose a compositional question outside the pre-modeled shapes and confirm
the system either returns a correctly composed answer or an explicit "outside current capability"
response — and never a fabricated answer.

**Acceptance Scenarios**:

1. **Given** a compositional question the system can compose from known steps, **When**
   processed, **Then** the system returns a correctly composed, sourced answer.
2. **Given** a compositional question the system cannot satisfy, **When** processed, **Then** the
   system states the question is outside current capability rather than returning a guess.

---

### Edge Cases

- A common name maps to multiple taxa (homonym) → the system disambiguates (US-6).
- A predicate exists only as a child term of the user's phrasing → roll-up is required (US-4/FR-006).
- A categorical predicate is phrased as if numeric (or vice versa) → the answer comes from the
  correct value slot (FR-005).
- A question is well-formed but compositional/novel → the US-7 path applies.
- Upstream returns an empty set for a correct query → US-8 ("no records found"), not a retry.
- Upstream is unavailable / times out / errors → explicit "upstream unavailable" outcome,
  distinct from "no records found" and from internal errors; no tight retry loop (FR-013).
- A user asks for something that would require a data change → the system refuses (FR-008).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept an unstructured natural-language biodiversity question as
  input.
- **FR-002**: The system MUST resolve user-mentioned attributes to EOL's controlled predicate
  terms before answering, and MUST NOT answer using an unverified term.
- **FR-003**: The system MUST resolve taxon references (scientific or common names) to EOL taxon
  identifiers, preferring identifier-based lookup to reduce homonym error.
- **FR-004**: The system MUST return results with provenance (source, resource, and
  citation/reference where available) so answers are traceable to EOL.
- **FR-005**: The system MUST correctly distinguish quantitative, categorical, and taxon-valued
  answers and present each appropriately.
- **FR-006**: When an attribute has sub-types, the system MUST roll them up when the user's
  question implies the general category (e.g., "size" includes "wingspan").
- **FR-007**: The system MUST cap result sizes and MUST surface when a result was truncated
  rather than silently returning a partial answer.
- **FR-008**: The system MUST never perform or imply any modification to the upstream data.
- **FR-009**: When a term or taxon cannot be confidently resolved, the system MUST ask for
  clarification rather than guess (see US-6).
- **FR-010**: The system MUST treat "no matching records" as a successful, explicit answer
  distinct from an error (see US-8).
- **FR-011**: For ecological associations, the system MUST preserve the correct relationship
  direction (see US-3).
- **FR-012**: The system MUST keep the underlying query language and upstream schema invisible to
  clients; changes upstream MUST NOT change the client-facing contract.
- **FR-013**: When the upstream (EOL) is unavailable, times out, or returns an error, the system
  MUST return an explicit "upstream unavailable" outcome that is distinct from both "no records
  found" (FR-010) and internal service errors. The system MUST NOT retry in a tight loop; it MAY
  perform a small bounded number of retries with backoff before surfacing the outcome.
- **FR-014**: Disambiguation (FR-009) MUST be stateless and single-shot from the service's
  perspective: the system returns the structured candidate set and the client resubmits the
  request with the chosen identifier. The service MUST NOT rely on holding multi-turn conversation
  state to resolve ambiguity.

### Key Entities *(include if feature involves data)*

- **Taxon / Page**: A biological grouping EOL describes, identified by a stable numeric page id
  and a canonical scientific name.
- **Trait**: A statement about a taxon, composed of a subject (the taxon), a predicate, and a
  value.
- **Predicate**: The kind of statement (e.g., "body mass", "habitat", "eats"), each backed by a
  controlled ontology term.
- **Value**: The content of a trait — categorical (a controlled term), quantitative (a
  measurement with units), or another taxon (for ecological associations).
- **Provenance**: The resource, contributor, citation, or reference behind a statement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a held-out set of questions covering the canonical shapes (US-1 through US-5),
  the system returns the correct records (verified against hand-written queries) at a target
  accuracy of at least 90%.
- **SC-002**: Zero answers are returned using an unresolved or invented ontology term (hard gate;
  any occurrence is a defect).
- **SC-003**: Zero upstream mutations are ever attempted (hard gate).
- **SC-004**: Ambiguous inputs produce a clarification prompt rather than a silent wrong answer in
  100% of a labeled ambiguity set (hard gate; any silent wrong answer on a labeled-ambiguous input
  is a defect).
- **SC-005**: Truncated results are always flagged; the test suite contains no instance of silent
  truncation.
- **SC-006**: For canonical-shape questions (US-1 through US-5), 95% of answers are returned within
  5 seconds end-to-end (p95 ≤ 5 s). Novel compositional questions (US-7) are excluded from this
  target.

## Assumptions

- The authoritative data source is the Encyclopedia of Life (EOL) trait database; "correct" means
  consistent with what hand-written queries against EOL return.
- Clients interact with the service through a structured request/response contract; users never
  author or see the underlying query language (FR-012).
- Result-size caps are configured deliberately by the service; the specific default cap is a
  planning-phase decision and is out of scope for this specification.
- A "successful" answer includes the explicit "no records found" outcome (FR-010) and the
  "outside current capability" outcome (US-7); neither is treated as an error.
- Read-only access to EOL is sufficient for every supported scenario; no scenario requires
  writing to the upstream (FR-008).
- The `literal` trait value slot is returned as pass-through display text (no quantitative,
  categorical, or taxon semantics) and is intentionally not exercised by a dedicated user story;
  generic mapping coverage (tasks T015) is sufficient.
