# Phase 1 Data Model: EOL Trait Query Service

Two model layers, kept strictly separate per Constitution I:

- **Upstream graph entities** — how EOL/neo4j is shaped (read-only, never exposed on the boundary).
- **Service contract entities** — what the service owns and returns to clients.

Mappers in `upstream/` translate the former into the latter. No upstream identifier shape, return
shape, or schema detail appears in a contract entity except where it is *deliberately* part of our
own contract (the `page_id` and the ontology `uri`, which are stable identifiers we choose to own).

---

## 1. Upstream graph entities (reference only — not the boundary)

Core statement pattern:

```
(:Page)-[:trait|inferred_trait]->(:Trait)-[:predicate]->(:Term)
```

| Node | Meaning | Key fields (subset) |
|------|---------|---------------------|
| `Page` | A taxon EOL describes | `page_id` (stable numeric), canonical scientific name |
| `Trait` | One statement about a Page | value slot (one of four, below) |
| `Term` | Controlled ontology term | `uri` (case-sensitive), `name`, `type` (`measurement`/`association`/value) |
| `Resource` | Dataset/source of a statement | resource id, name |
| `Vernacular` | Common name for a Page | name, language |
| `MetaData` | Statement metadata | citation/reference fields |

**Trait value slots** (exactly one populated, by predicate type):

| Slot | Value kind | Maps to contract `Value.kind` |
|------|-----------|-------------------------------|
| `object_term` | categorical (a controlled `Term`) | `categorical` |
| `object_page` | taxon association (another `Page`) | `taxon` |
| `normal_measurement` | quantitative, normalized (+ units) | `quantitative` |
| `literal` | free literal | `literal` |

**Traversals used by shapes**:
- Statement: `(:Page)-[:trait|inferred_trait]->(:Trait)-[:predicate]->(:Term)`
- Term roll-up (sub-types): `-[:parent_term|synonym_of*0..]->`
- Lineage: `Page` parent chain (US-5)
- Association direction is significant and asserted (e.g., `RO_0002471` = *eaten by*).

---

## 2. Service contract entities (the boundary)

### Taxon
Stable taxon reference the service owns.
- `page_id`: integer (stable EOL page id) — the canonical identifier we resolve to and return.
- `scientific_name`: string (canonical).
- `vernacular_names`: list of `{name, language}` (optional, for display/disambiguation).

**Rules**: Resolution prefers `page_id` lookup over name matching (FR-003) to avoid homonyms.
A taxon is never returned without a `page_id`.

### Predicate
A resolved attribute, backed by a controlled term.
- `uri`: string, **case-sensitive** (e.g., `VT_0001259`).
- `name`: human label (e.g., "body mass").
- `type`: enum `measurement | association | categorical`.

**Rules**: A predicate on the boundary MUST have come from resolution (R1); URIs are never
model-authored (Constitution II validator gate). Case is preserved verbatim.

### Value (tagged union by `kind`)
- `kind = quantitative`: `{ amount: number, units: string, normalized: bool }`
- `kind = categorical`: `{ term: Predicate-like {uri, name} }`
- `kind = taxon`: `{ taxon: Taxon, direction: enum subject_to_object | object_to_subject }`
- `kind = literal`: `{ text: string }`

**Rules**: The correct slot is chosen by predicate type (FR-005). For `taxon` values the
`direction` field is mandatory and asserted across hops (FR-011, R7).

### Provenance
Traceability for a statement (FR-004).
- `resource`: `{ id, name }` (optional)
- `contributor`: string (optional)
- `citation`: string (optional)
- `reference`: string (optional)

**Rules**: Attached to every returned statement where EOL supplies it; absence is recorded
explicitly, not silently dropped.

### Statement
One answer row.
- `subject`: Taxon
- `predicate`: Predicate
- `value`: Value
- `provenance`: Provenance

### CandidateSet (for disambiguation, FR-009/US-6/FR-014)
- `kind`: enum `taxon | predicate`
- `candidates`: list of Taxon **or** Predicate, ranked, each with a resolution score.

### Result (tagged union of outcomes) — the response envelope
All five outcomes are first-class; none is an error overload.

| `outcome` | Payload | Source requirement |
|-----------|---------|--------------------|
| `answer` | `statements: [Statement]`, `count?: int`, `truncated: bool`, `cap: int` | FR-004/005/006/007 |
| `no_records` | (empty) explicit "EOL has no such record" | FR-010 / US-8 |
| `needs_clarification` | `CandidateSet` | FR-009 / US-6 |
| `upstream_unavailable` | `detail` | FR-013 |
| `out_of_capability` | `reason` | US-7 |

**Rules**:
- `truncated` is **always** present on `answer`; set true when a result cap was hit (SC-005). Never
  silent truncation, including per-hop intermediate truncation in chains (R7).
- `count` is the rolled-up aggregate for US-4; roll-up uses term sub-type expansion (FR-006).
- The envelope carries no Cypher, no neo4j row shape, no raw schema identifiers (Constitution I).

---

## 3. Intent entities (internal — service-side, not on the boundary)

### QueryIntent (output of the Mellea-constrained extractor)
Format-valid typed object; **semantic** validity is established later by resolution + validator.
- `shape`: enum of known shapes (`single_fact`, `categorical_attribute`, `association`,
  `aggregate_count`, `lineage`, `n_hop_chain`) or `novel`.
- `taxon_refs`: list of raw taxon mentions (pre-resolution).
- `predicate_refs`: list of raw attribute mentions (pre-resolution).
- `rollup`: bool (does the question imply the general category? FR-006).
- `direction_hint`: optional (for associations).
- `hops`: ordered list of per-hop `{predicate_ref, direction}` for `n_hop_chain`.

**Rules**: `shape != novel` MUST be served by a versioned template (Constitution III). `novel`
routes to the calling-model decomposition path. Raw refs are resolved to `Taxon`/`Predicate`
before any query is built; unresolved refs trigger `needs_clarification`, never a guess.

### ResolvedQuery (template/tool output, validator input)
- `cypher`: string (with mandatory `LIMIT`)
- `referenced_uris`: list of URIs used (all must trace to resolution)
- `read_only`: derived/asserted

### RepairAttempt (versioned repair loop, R8)
- `rule_id`, `rule_version`, `trigger`, `transform`, `outcome`, `captured_miss: bool`

### TraceContext (Constitution VI)
- `request_id`, `layer` (`client-orchestrator` | `service-extractor`), `model_id`,
  `tokens_in/out`, `cost`, `latency_ms` — attached to every span.

---

## 4. Lifecycle (request → result)

```
NL question
  → extract (Mellea → QueryIntent)            [layer: service-extractor]
  → resolve taxon_refs / predicate_refs        [retrieval over embedded catalog]
      ↳ low confidence → Result.needs_clarification (CandidateSet)   [stateless, FR-014]
  → build ResolvedQuery from versioned shape (or route novel → client tools)
  → VALIDATOR (LIMIT, URIs resolved, read-only)  [single choke point, no bypass]
  → run_cypher (JWT, format=cypher, caps, bounded retry)  [upstream]
      ↳ empty            → Result.no_records (FR-010)
      ↳ timeout/error    → Result.upstream_unavailable (FR-013)
  → map neo4j → Statements + Provenance; set truncated/count
      ↳ repair rule applies → re-resolve/re-shape → VALIDATOR → run_cypher (bounded)
  → Result.answer
```

Every transition emits a layer-tagged span; the validator is on the only path to `run_cypher`.
