# Contract: Client-Facing Boundary

The only surface clients depend on. Cypher, the EOL schema, and neo4j return shapes are invisible
here (Constitution I). Field shapes mirror `data-model.md` §2.

## Endpoint

`POST /v1/answer`

### Request

```json
{
  "question": "how heavy is a sea otter?",
  "chosen": { "kind": "taxon", "page_id": 328583 },
  "max_results": 100
}
```

- `question` (required): unstructured natural-language biodiversity question (FR-001).
- `chosen` (optional): a disambiguation selection echoed back from a prior `needs_clarification`
  response (FR-014, stateless). `kind` ∈ `taxon | predicate`; carries the chosen `page_id`/`uri`.
- `max_results` (optional): client hint, clamped to the service's deliberate cap (Constitution VII).

### Response — tagged by `outcome`

A 200 response always carries one of five outcomes (errors are not overloaded onto failures of
data availability):

```json
// answer
{
  "outcome": "answer",
  "statements": [
    {
      "subject": { "page_id": 328583, "scientific_name": "Enhydra lutris" },
      "predicate": { "uri": "VT_0001259", "name": "body mass", "type": "measurement" },
      "value": { "kind": "quantitative", "amount": 25.0, "units": "kg", "normalized": true },
      "provenance": { "resource": { "id": 42, "name": "PanTHERIA" }, "citation": "..." }
    }
  ],
  "count": null,
  "truncated": false,
  "cap": 100
}
```

```json
{ "outcome": "no_records" }                                   // FR-010 / US-8
```

```json
// needs_clarification — FR-009 / US-6, stateless
{
  "outcome": "needs_clarification",
  "candidates": {
    "kind": "taxon",
    "items": [
      { "page_id": 328583, "scientific_name": "Enhydra lutris", "score": 0.91 },
      { "page_id": 46559421, "scientific_name": "Lontra felina", "score": 0.40 }
    ]
  }
}
```

```json
{ "outcome": "upstream_unavailable", "detail": "EOL timed out" }   // FR-013
```

```json
{ "outcome": "out_of_capability", "reason": "novel multi-hop composition not modeled" }  // US-7
```

## Invariants (testable)

- **C1**: No response field ever contains Cypher text, a neo4j row object, or an EOL internal schema
  label (Constitution I; conformance test scans every field).
- **C2**: `answer.truncated` is always present; `true` iff a result cap was hit (SC-005). No silent
  truncation, including intermediate-set truncation in chains.
- **C3**: Every `statement` carries `provenance` when EOL supplies it; missing provenance is null,
  never silently omitted (FR-004).
- **C4**: `value.kind` matches the predicate type — quantitative/categorical/taxon/literal in the
  correct slot (FR-005).
- **C5**: `taxon` values carry `direction`; it is never inverted (FR-011).
- **C6**: Aggregate questions return `count` rolled up over term sub-types (FR-006 / US-4).
- **C7**: `needs_clarification` is returned (not a guess) whenever resolution confidence is below
  threshold (FR-009; SC-004 hard gate).
- **C8**: `outcome` is one of exactly five values; `no_records`, `upstream_unavailable`, and
  `out_of_capability` are distinct and never collapsed into one another.
