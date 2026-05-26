# DECISIONS

Every meaningful ambiguity I resolved, what I chose, and why.

---

## SAP export format: ALV CSV, not IDoc or OData

**Alternatives considered:** IDoc (XML/flat file EDI), OData REST (S/4 HANA Fiori), BAPI (RFC function call), ABAP report to file.

**Chosen:** ALV CSV flat file.

**Why:** The assignment says the client has "fuel and procurement data sitting in SAP." In practice, when a sustainability team asks an SAP team for a data extract, the response is almost always: "I'll run an ME2M / ME80FN report and save the ALV grid to a file." IDoc requires a configured EDI partner profile — these are set up for inter-company transactions, not sustainability reporting. OData requires S/4 HANA (many large Indian enterprises are still on ECC 6.0) and API client credentials. BAPI requires an ABAP developer to write a caller. The ALV CSV requires only a basic SAP user who can run a standard report.

The cost: ALV CSV has no schema. Column names vary by system language, client configuration, and which transaction the report was run from. I handled this by building a column alias map that covers both English and German field labels, plus field names (MAKTX, MEINS, etc.) for systems configured to export technical names.

**What I'd ask the PM:** "Has the client's SAP team confirmed they can run an MM report with fuel/procurement GR lines? Do they know if the system is ECC 6.0 or S/4? What's the system language configured as?"

---

## Subset of SAP data handled

**Handled:**
- Goods Receipt (GR) lines for fuel materials (diesel, petrol, HSD, LPG, natural gas, furnace oil)
- Identification by material description (MAKTX) keyword matching, including German material names
- Unit codes: L, Ltr, LTR, KL, KG, M3, GAL, UGAL, GL
- Date fields: BLDAT (document date) and BUDAT (posting date), with SAP-specific date formats (YYYYMMDD, DD.MM.YYYY)
- Plant code lookup (T001W equivalent — hardcoded for demo)
- Cost center to infer mobile vs stationary combustion

**Ignored:**
- Purchase Orders (PO header, open POs without GR) — we only count actual consumption, not commitments
- Services procurement (IT, consultancy) — no emission factor applicable
- Direct Procurement (FI document lines without MM) — different table structure
- Intercompany transfers — double-counting risk
- Partial deliveries / returns — would require netting logic
- Batch/serial number tracking
- Multi-currency conversion — we store local currency for reference only

**What I'd ask the PM:** "Does the client track fuel in the MM module with GR postings? Or do they use FI direct expense coding? Any chance fuel is coded as a service rather than a material?"

---

## Utility data: portal CSV export, not PDF, not API

**Alternatives considered:** PDF bill (OCR or native text extraction), utility API (Green Button, DISCOM portal API), manual data entry.

**Chosen:** Portal CSV export.

**Why:**
- PDF parsing: Indian DISCOM bills have wildly inconsistent layouts across providers (BSES Delhi, MSEDCL Maharashtra, BESCOM Karnataka, TNEB Tamil Nadu all differ). Template-based OCR breaks on bill redesigns. pdfminer/pymupdf text extraction works for digital PDFs but fails on scanned images (common for older bills). Too unreliable for an MVP.
- API: No Green Button equivalent in India. DISCOM portal APIs are not publicly documented. Would require client-specific integration per DISCOM.
- Portal CSV: All major Indian DISCOMs offer account portal downloads with CSV/Excel export. The sustainability team already accesses this portal to pay bills. Format is more stable than PDF and more accessible than API.

**What I'd ask the PM:** "How many meters across how many DISCOMs are we dealing with? If it's 200+ meters, the manual portal export becomes a bottleneck and we'd want to explore DISCOM-specific automation."

---

## Billing period handling for electricity

Billing periods do NOT align with calendar months. An MSEDCL bill might run from Jan 7 to Feb 6. I store `period_start` and `period_end` as-is, not coerced to a calendar month.

For annual reporting, emissions are allocated to the reporting year based on period overlap. If a bill's period spans two years, a strict interpretation would pro-rate. We flag bills with >45-day periods as suspicious (may be catch-up bills) and <20-day periods (partial bills, meter replacement). Pro-ration across years is not implemented — this is noted in TRADEOFFS.md.

---

## Travel data: Concur/Navan CSV export, not API

**Alternatives considered:** SAP Concur Reporting API (JSON), Navan API, TripActions API, manual entry.

**Chosen:** CSV expense report export.

**Why:** The Concur Reporting API requires OAuth2 tokens issued per company, which requires the client's Concur admin to create an API application and generate credentials. That's a non-trivial setup for a prototype. The CSV export is a built-in feature every Concur user has access to, and travel managers already run expense reports regularly. The CSV format is close enough to the Navan export that a single parser handles both.

**Subset handled:** Flights (with IATA airport code distance computation), hotels (room-nights), ground transport (distance or amount fallback). Not handled: ferry, train (rail category exists but emission factor is approximate), chartered aircraft, private jet (no standard factor).

---

## Distance computation for flights

When the travel CSV doesn't include distance (which is common — Concur doesn't always export it), I compute great-circle distance via haversine from IATA airport codes.

**Why haversine and not a routing API?** No API key dependency. Great-circle is a reasonable approximation for long-haul (within 5-10% of actual route for most flights). Short-haul routes can deviate more due to air traffic routing, but the difference is within the uncertainty of the emission factor itself.

**Limitation flagged:** Every haversine-computed distance gets a warning on the record: "Distance computed via haversine — verify against actual flight path." The built-in airport database covers ~150 airports; unknown airports produce an error.

**What I'd ask the PM:** "Does the client's travel platform output flight distances? Concur does sometimes include this in the 'Itinerary' report type but not in the standard expense export."

---

## Cabin class defaulting

If cabin class is missing from the travel export, I default to Economy and flag it. Economy is the most common class and the most conservative for Scope 3 accounting (underreporting business class emissions is a real risk). I do not default to Business, which some tools do — that would be overstating emissions, which creates audit problems.

---

## Emission factors: DEFRA 2023, India CEA

**Why DEFRA for fuel and travel instead of IPCC or EPA?**
DEFRA publishes annually updated, comprehensively cited conversion factors covering all major fuel types and travel modes. They include CH4 + N2O in the CO2e total (using AR5 GWP100). They're widely accepted by Indian auditors because most third-party verifiers (Bureau Veritas, DNV, SGS) use DEFRA or equivalent UK/EU factors. GHG Protocol doesn't publish its own factors — it points to national factor databases.

**Why India CEA for electricity?**
The GHG Protocol Scope 2 Guidance requires either a location-based or market-based factor. For location-based accounting, the nationally appropriate factor is CEA's CO2 Baseline Database (FY 2022-23: 0.716 kg CO2e/kWh). This is the factor used by the Bureau of Energy Efficiency (BEE) and mandated under India's Carbon Credit Trading Scheme (CCTS) framework. We store this per-org and allow override for market-based accounting (green tariff, REC purchase).

---

## Review workflow: status transitions

`pending → approved | rejected | flagged`, `pending ← approved | rejected | flagged` (reversible), `approved → locked` (irreversible).

I chose not to auto-approve any records, even ones with no warnings. An analyst's eyes on every record is the entire point of the system. The lock is a one-way door because once data goes to auditors, retroactive changes create auditability problems.

---

## Authentication: JWT, not sessions

DRF + React SPA architecture. Session cookies work fine for Django-rendered apps but require CSRF handling and SameSite config when the frontend and backend are on different domains (common in deployment). JWT stored in localStorage is simpler for a cross-origin SPA. Tradeoff: localStorage is vulnerable to XSS; httpOnly cookies are more secure. Documented in TRADEOFFS.md.

---

## Django `apps/` package structure

I put apps in an `apps/` subdirectory (`apps.accounts`, `apps.ingestion`) rather than top-level. This keeps the project root clean and matches the structure of larger Django projects where dozens of apps would otherwise clutter the root. It requires explicit `label` in each `AppConfig` to avoid collisions.
