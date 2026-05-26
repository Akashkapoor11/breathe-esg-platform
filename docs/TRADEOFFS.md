# TRADEOFFS

Three things I deliberately did not build, and why.

---

## 1. Deduplication across ingestion jobs

**What it is:** If the same SAP document (by document number) or same utility bill (by meter + billing period) is uploaded twice, we currently create duplicate `EmissionRecord` rows. There is no uniqueness constraint on `(org, source_ref)`.

**Why not built:**
The correct deduplication logic depends on business rules I don't have enough information to define without client input. Consider:

- **SAP reversal documents:** In SAP, a GR (Goods Receipt) can be reversed with a negative-quantity GR. The reversal has a different document number. If we deduplicate on document number, we miss the reversal. If we sum by document number, we need to know which documents are reversals. This requires understanding the `BWART` (movement type) field, which I parsed but didn't act on.
- **Utility bill amendments:** DISCOMs sometimes issue amended bills for the same period (billing errors, meter replacements). An amended bill for the same meter+period is not a duplicate — it supersedes the original. But the system can't know that without a bill amendment flag in the CSV.
- **Travel resubmissions:** Expense reports can be recalled and resubmitted in Concur. Trip IDs may change between submissions.

**The honest answer:** Deduplication is a business rule, not a technical rule. An analyst reviewing records will spot duplicates via the `source_ref` filter. Automating it requires knowing which field is the real primary key in the source system and how amendments are represented — that's a client-specific question.

**What I'd build next:** A "suspect duplicates" tab in the dashboard that shows records with identical `source_ref` values within an org. Let the analyst decide which to reject.

---

## 2. Pro-ration of billing periods across reporting years

**What it is:** If a utility bill covers Dec 15 2023 – Jan 14 2024, a portion of the emissions belongs to 2023 and a portion to 2024. The current system assigns the entire bill to the year in which it falls, based on `period_start`. This is incorrect for cross-year bills.

**Why not built:**
Pro-ration requires a policy decision: do we pro-rate by days, by energy distribution (if sub-metering is available), or by some other method? The GHG Protocol does not mandate a single approach. Most companies use a simpler rule: assign to the reporting period in which the invoice date falls. Some use billing period midpoint. Some pro-rate by days.

The right answer is: ask the client what their auditor expects. Until that's decided, building a pro-ration algorithm locks in a policy choice that may conflict with the client's existing reporting methodology.

**The workaround:** We flag bills with periods crossing year boundaries in `warnings`. The analyst can review and decide. If pro-ration is needed, the raw data is preserved and the logic can be applied in a post-processing step.

**What I'd build next:** A `reporting_period_start` / `reporting_period_end` on the `Organization` model, plus a pro-ration field on `EmissionRecord` that stores the fraction allocated to the current reporting period. Run as a separate calculation step after ingestion, with the methodology configurable per org.

---

## 3. Real-time API pulls (SAP OData, DISCOM APIs, Concur API)

**What it is:** Instead of file uploads, the system would periodically call SAP's OData API, the utility company's data API, and Concur's Reporting API to pull fresh data automatically.

**Why not built:**
**Scope:** Each API pull requires OAuth2 or API key credentials, client-specific configuration, and error handling for rate limits, token expiry, and source system downtime. Implementing this reliably for three different sources would take more than four days and would produce infrastructure-heavy code that's hard to evaluate without live credentials.

**Correctness concerns:** A file upload has a clear source-of-truth — the uploaded file is the evidence. An API pull that fails silently (network timeout, API returns partial data) is harder to detect and audit. The file-based approach makes the evidence artifact explicit: every record traces back to a specific uploaded file at a specific timestamp.

**Practical reality:** Most enterprise clients don't have API access configured for sustainability reporting. The SAP OData API requires an SAP BASIS team to enable and the Fiori launchpad to be configured. The Concur API requires an app registration and OAuth flow approved by the company's IT department. File exports work today with zero IT involvement.

**What I'd build next:** A `DataSource` model that configures API credentials per org per source type. A Celery beat task that pulls data on a schedule and creates `IngestionJob` records the same way a file upload does — same parsers, same model, same review flow. The UI would show "auto-pulled" jobs alongside manually uploaded ones, with the last-pull timestamp and next-scheduled-pull visible in the dashboard.
