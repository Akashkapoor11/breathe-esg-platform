# DATA MODEL

## Core design principles

**Immutability of source data.** Every ingested row stores a verbatim `raw_data` JSON copy of the original CSV row. This is never mutated after creation. The normalized fields (`activity_value_normalized`, `co2e_kg`) are derived values. If you need to re-run normalization, you re-derive from `raw_data` — you don't re-fetch from the source, because the source may have changed.

**Full traceability.** Every number on every record can be traced: `co2e_kg = activity_value_normalized × emission_factor`. The factor is stored with its source citation string. The unit conversion path is stored in `warnings`. An auditor can reconstruct the entire calculation from fields on the record alone, without consulting an external database.

**Append-only audit.** `AuditEvent` is never updated or deleted. Every status transition — ingested, approved, rejected, flagged, locked — creates a new row. Actors are denormalized into `actor_name` so the trail is readable even if the user account is later deleted or anonymized.

---

## Entity overview

```
Organization
└── CustomUser (role: admin | analyst | viewer)
└── IngestionJob (one per uploaded file)
    └── EmissionRecord (one per source row that yielded a valid emission)
        └── AuditEvent (one per lifecycle event on the record)
```

---

## Multi-tenancy

Every model has a FK to `Organization`. All DRF viewsets filter `get_queryset()` by `request.user.organization` before any other filtering. There is no superuser pathway that would allow cross-org reads in the API layer — only the Django admin (accessible only via `is_staff`) bypasses org scoping.

Why not row-level security in PostgreSQL? We considered it. The tradeoff: Django ORM `filter(org=...)` is explicit, readable, and testable. PostgreSQL RLS requires a session variable set at connection time, which is fragile in a connection-pooled environment (PgBouncer / Render's internal proxy). We enforced it at the application layer and documented the risk.

---

## Scope 1/2/3 categorization

We follow the GHG Protocol Corporate Standard (2015 revision).

| Scope | Category (our key) | What it covers | Source |
|---|---|---|---|
| 1 | `stationary_combustion` | Boilers, generators, furnaces — fuel burned at fixed assets | SAP |
| 1 | `mobile_combustion` | Fleet vehicles, forklifts — fuel burned in owned/leased transport | SAP |
| 2 | `purchased_electricity` | Grid electricity drawn from utility | Utility |
| 3 | `business_travel_air` | Employee flights | Travel |
| 3 | `business_travel_hotel` | Hotel nights | Travel |
| 3 | `business_travel_ground` | Taxis, rental cars, ride-hailing | Travel |
| 3 | `business_travel_rail` | Train journeys | Travel |

Scope 1 vs Scope 2 is determined at parse time by source type: SAP → Scope 1, Utility → Scope 2. Within Scope 1, `stationary` vs `mobile` is inferred from material description and cost center keywords (fleet, vehicle, boiler, generator). This is imperfect and flagged in warnings when the classification is uncertain.

Scope 3 categories are determined by the `Type` column in the travel export (FLIGHT, HOTEL, CAR, RAIL). Unknown types produce a parse warning and the row is skipped.

---

## `IngestionJob` — one per uploaded file

Tracks the provenance of a batch of records. Once complete, it is immutable — we never re-process a job. If a file needs to be re-ingested (e.g., the emission factor changed), a new upload creates a new job, and analysts reject the old records.

Key fields:
- `source_type`: SAP | UTILITY | TRAVEL — determines which parser runs
- `filename`: original file name, stored for human reference
- `uploaded_by`: FK to user — who triggered the ingestion
- `row_count` / `success_count` / `error_count`: summary counters, set atomically after processing
- `processing_log`: JSON list of `{level, row, message}` — the full parse trace
- `status`: PENDING → PROCESSING → COMPLETE | FAILED | PARTIAL

---

## `EmissionRecord` — one per emission event

The canonical normalized record. One row in the source CSV produces zero or one `EmissionRecord`. Rows that can't be parsed (missing date, zero quantity, unrecognized unit) produce an error in `processing_log` but no record.

### Source-of-truth tracking

| Field | Purpose |
|---|---|
| `raw_data` | Verbatim CSV row dict. Never mutated. |
| `job` | FK to the IngestionJob — which file, when, who uploaded |
| `source_ref` | Human-readable identifier from the source system (SAP doc number, meter ID, trip ID). Unique within a source system. Used for deduplication checks. |

### Unit normalization chain

```
raw: activity_value (activity_unit)
    ↓ unit conversion (see SAP/Utility/Travel parsers)
normalized: activity_value_normalized (activity_unit_normalized)
    × emission_factor (emission_factor_unit)
    = co2e_kg
```

The standard unit per category:
- Fuel combustion → Litres (L) or cubic metres (m³) for gas
- Electricity → kWh
- Air travel → passenger-km
- Hotel → room-nights
- Ground → km

### Why store both raw and normalized?

If our unit conversion logic had a bug, we need to be able to re-derive the normalized value without going back to the source system. `raw_data` + parser code is sufficient to reproduce the normalized value deterministically.

### The `warnings` field

A JSON list of human-readable strings describing data quality issues found during parsing:
- Unit assumptions ("Unit 'Ltr' normalized to L")
- Missing data ("No plant code — location unknown")
- Computed values ("Distance DEL→BOM computed via haversine, verify with routing")
- Outliers ("Quantity 800,000 L — verify not a sum row")
- Cross-checks ("Our CO₂e differs from vendor-reported by 34% — different methodology likely")

Any record with non-empty `warnings` is surfaced in the dashboard and filterable in the review table.

### Review workflow

```
pending → (analyst: approve | flag | reject)
                ↓
         approved → (admin: lock_for_audit)
                         ↓
                   is_locked = True (immutable)
```

A record can be cycled back to `pending` from any non-locked state. Once locked, no fields can change. Locking requires `status == 'approved'` — you cannot lock a flagged or pending record.

### Edit history

The `edit_history` JSON field on `EmissionRecord` stores a list of `{timestamp, actor, field, old, new}` for any field edits made via the admin or a future edit API. Today only review status changes are tracked here (duplicate of AuditEvent, but kept for the record itself to be self-contained).

---

## `AuditEvent` — append-only event log

Never updated, never deleted. Each row records:
- `record`: FK to EmissionRecord
- `action`: ingested | approved | rejected | flagged | pending | edited | locked
- `actor` + `actor_name`: denormalized to survive user deletion
- `timestamp`: `auto_now_add`, set by the database
- `data_before` / `data_after`: JSON snapshots of changed fields
- `note`: analyst's comment at the time of action

The combination of `AuditEvent` rows for a record reconstructs its complete lifecycle for a third-party auditor.

---

## Emission factor storage

Factors are stored on the `EmissionRecord` itself, not looked up at query time. This means:
1. If the factor database is updated in a future year, historical records still show the factor that was applied.
2. An auditor can verify the factor without needing access to our internal factor database.
3. The `emission_factor_source` string gives a citable reference (DEFRA 2023 Table 1A, CEA Version 18.0).

The `Organization` model stores a per-org electricity factor (for market-based Scope 2 accounting, e.g., if the client has a green tariff or RECs). The default is the India CEA grid average (0.716 kg CO₂e/kWh, FY 2022-23).

---

## Indexes

```python
Index(['org', 'status'])          # main review queue filter
Index(['org', 'scope'])           # scope breakdown queries
Index(['org', 'period_start', 'period_end'])  # date range filtering
Index(['job'])                    # records per job
Index(['is_locked'])              # audit export filter
```

---

## What this model does NOT do

- **No real-time deduplication** across jobs. If the same SAP document number appears in two uploads, both produce records. A uniqueness check on `(org, source_ref)` would catch this but creates problems when legitimate amendments are uploaded. Deduplication is left to the analyst review process (a `source_ref` filter in the UI would surface duplicates).
- **No emission factor versioning table.** Factors are embedded in each record. A separate `EmissionFactor` model with effective dates would be cleaner if we needed to re-run all historical calculations after a factor update.
- **No real-time multi-user conflict detection.** If two analysts approve/reject the same record concurrently, the last write wins. Acceptable for the scale of this prototype.
