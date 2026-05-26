# SOURCES

For each of the three data sources: what real-world format I researched, what I learned, what the sample data looks like and why, and what would break in a real deployment.

---

## 1. SAP Fuel & Procurement

### Real-world format researched

SAP exports fuel and procurement data through the MM (Materials Management) module. The primary transactions for extracting GR (Goods Receipt) data are:

- **ME2M** — Purchase orders by material. Outputs PO lines with MATNR (material number), MAKTX (material description), MENGE (quantity), MEINS (unit of measure), WERKS (plant), KOSTL (cost center), BLDAT (document date), BUDAT (posting date), BELNR (document number).
- **ME80FN** — Purchasing reporting with GR/IR matching. More complex, includes partial deliveries.
- **MB51** — Material Document List. Shows all goods movements, including GR (movement type 101), returns (102), and reversals (102 against 101).

The ALV (ABAP List Viewer) grid can be exported via **List → Save → Local file → Spreadsheet** or directly to a `.CSV`. This is the standard method used by sustainability leads at clients without dedicated ESG tools.

**German header problem:** SAP system language is set per client, not per user. If `SY-LANGU = DE`, the field labels in the ALV export are German: "Werk" instead of "Plant", "Menge" instead of "Quantity", "Buchungsdatum" instead of "Posting Date". Our column mapping handles both.

**SAP unit codes:** SAP uses its own unit codes (MEINS field). Common ones:
- `L` or `Ltr` = litre
- `KL` = kilolitre (1000 L)
- `KG` = kilogram (requires density conversion to volume)
- `M3` = cubic metre (for gas)
- `GAL`, `UGAL` = US gallon

**Date formats:** The BLDAT/BUDAT field in ALV exports can appear as `YYYYMMDD` (SAP internal), `DD.MM.YYYY` (German locale), or `MM/DD/YYYY` (EN-US locale). We try all formats.

**Plant codes:** The WERKS field contains codes like `1000`, `PLNT_DEL`, or client-specific abbreviations. These are meaningless without T001W (the plant master data table). In a real deployment, we'd join to T001W to get the plant name and country, which determines the location-based grid factor for Scope 1 calculations.

### What our sample data looks like and why

Our sample SAP CSV (`MM_fuel_procurement_Jan2024.csv`) contains four rows representing:
1. 5,000 L diesel purchase, Delhi fleet — straightforward, no warnings
2. 2,500 L petrol purchase, Mumbai fleet — German material description ("Benzin") to test German header handling
3. 1,200 m³ natural gas, Bangalore boiler — to test gas unit (M3) and stationary combustion classification
4. 800 KL HSD, Chennai — to test kilolitre unit conversion AND the large-quantity outlier flag (800 KL = 800,000 L is unusually large and gets flagged)

We deliberately included a German material description and a large-quantity outlier because these are the two most common data quality issues we'd see from Indian enterprises with SAP systems configured in German.

### What would break in a real deployment

1. **Unknown material codes:** Our fuel identification relies on MAKTX keyword matching. If the client codes diesel as "Grade A Petroleum Product" or "D-Fuel" without standard keywords, it gets skipped as non-fuel procurement. We'd need to load the client's material master (MM60 or MARA table export) and map MATNR codes explicitly.

2. **Multiple company codes:** A large enterprise has multiple BUKRS (company codes) in one SAP system. Emissions should be consolidated across all, but some subsidiary plant codes may have different reporting obligations. We'd need to configure which company codes to include.

3. **GR reversals:** Movement type 102 (GR reversal) produces a negative MENGE. Our parser skips zero-or-negative quantities. This means reversed transactions are dropped silently rather than netting against the original. We'd need to match 101/102 pairs or explicitly track negative quantities as offsets.

4. **Blend fuels:** If diesel is a biodiesel blend (B7, B20), the emission factor changes. SAP doesn't typically track blend percentages in MAKTX. This would require either a material classification setup in SAP or a lookup table.

5. **Inter-company transfers:** If diesel is transferred from one plant to another, both the issue and receipt appear in MB51. We'd double-count unless we filter by movement type to only count external GRs (mvt type 101 from external vendor).

---

## 2. Utility Electricity

### Real-world format researched

Indian DISCOMs (Distribution Companies) serve different states:
- Delhi: BSES Rajdhani, BSES Yamuna, Tata Power Delhi
- Maharashtra: MSEDCL, Adani Electricity (Mumbai)
- Karnataka: BESCOM, HESCOM, MESCOM
- Tamil Nadu: TNEB/TANGEDCO
- Gujarat: MGVCL, DGVCL, PGVCL, UGVCL

All of them offer web portal account access where account holders can download billing history as CSV or Excel. The exact schema varies but consistently includes:

- **Account number / Meter ID:** Usually the CA (consumer account) number and meter serial number
- **Billing period:** Start and end dates (the problem: they rarely align with calendar months)
- **Consumption:** In kWh (some portals say "Units" — 1 unit = 1 kWh)
- **Peak demand:** In kW (for HT/EHT consumers billed on demand+consumption tariff)
- **Amount:** Total bill amount in INR
- **Tariff category:** Commercial LT, Industrial HT, EHT, etc.

Some enterprise clients (HT consumers, >100 kW) receive monthly data files directly from the DISCOM — a CSV with multiple meter readings if they have interval metering (15-minute demand intervals). We don't handle interval data in this prototype; we assume monthly billing summaries.

### What our sample data looks like and why

Our sample `electricity_Q1_2024_all_sites.csv` contains three rows:
1. Delhi main plant, meter MTR-001A — billing period Jan 5 to Feb 4 (31 days, crosses months) to demonstrate non-calendar alignment
2. Delhi warehouse, meter MTR-001B — same account, second meter, demonstrates one account can have multiple meters
3. Mumbai IT park, meter MTR-002A — clean calendar-month billing for comparison

The Delhi billing period deliberately doesn't align with calendar months because every real DISCOM we researched bills in ~30-day cycles starting from meter installation date, not January 1. This is the most common surprise for clients who assume electricity data fits neatly into quarterly reporting.

### What would break in a real deployment

1. **PDF bills instead of portal CSV:** Many smaller facilities still receive paper bills or email PDF bills and don't have portal access configured. PDF extraction (pdfminer, PyMuPDF) would need template-per-DISCOM because the layout is not standardized. MSEDCL bills look completely different from BESCOM bills.

2. **Different column names per DISCOM:** Our column alias map covers common variants. But a DISCOM might use "Energy Charges (kWh)" as the column header for consumption, which doesn't match any of our aliases. We'd need to add portal-specific column maps.

3. **MWh vs kWh confusion:** Large industrial consumers are sometimes billed in MWh. If the portal exports "Units: 45.23" meaning MWh (not kWh), we'd undercount by 1000x. We flag unusually large values (>1,000,000 kWh in one period) but can't catch the reverse (small MWh values that look like plausible kWh).

4. **Sub-metering:** A single facility may have dozens of sub-meters for different production areas. The portal might export each sub-meter as a separate row, or aggregate them. Without knowing the metering topology, we can't tell if rows should be summed or represent the same consumption.

5. **Market-based vs location-based:** For Scope 2, GHG Protocol allows market-based accounting (using the supplier-specific emission factor from a green tariff or REC). Our default is location-based (CEA grid average). If the client has a green power agreement, they need to upload their REC certificates and override the factor per meter. Not implemented.

6. **T&D losses:** Some reporting frameworks require adding transmission and distribution losses to the consumed kWh before applying the emission factor. We don't add T&D losses — this should be confirmed with the client's auditor.

---

## 3. Corporate Travel

### Real-world format researched

**Concur (SAP Concur):** The dominant corporate travel and expense platform in India for large enterprises. Expense reports can be exported via the Reporting module. The "Expense Report" export includes one row per expense line within a trip. Relevant fields: Report ID, Employee ID, Expense Type (Air, Hotel, Ground), Departure Date, Merchant Name, Amount, Currency.

Concur's Itinerary export (separate from Expense Report) includes Origin/Destination city/airport, Departure/Arrival datetime, Cabin Class, Ticket Number. The two exports are joined by Report ID or Trip ID. In practice, clients export one of these; we handle the combined/flattened version.

**Navan (formerly TripActions):** Growing market share in Indian tech companies. Similar export schema. Differences: Navan sometimes pre-calculates CO2 emissions (using ICAO methodology without radiative forcing). We capture this in `co2_reported` and compare against our calculation — deviations >30% get a warning.

**Key variables in travel emissions:**
- **Distance:** Often not in the export. If IATA origin/destination are present, we compute via haversine. If not, the row fails.
- **Cabin class:** Economy, Premium Economy, Business, First. DEFRA 2023 has separate factors for each. First class long-haul is 5.6x economy long-haul (higher seat pitch = more allocated aircraft weight/fuel per passenger).
- **Radiative forcing (RF) multiplier:** Flying at altitude creates additional warming effects beyond CO2 (NOx, contrails, cirrus cloudiness). DEFRA 2023 includes an RF multiplier (~1.891 for short-haul, ~2x for long-haul) in its flight factors. Not all platforms include RF. We include it because GHG Protocol Aviation Supplement recommends it and UK SECR mandates it.

**Distance threshold for haul type:** DEFRA defines short-haul as <3,700 km. This is their definition — other databases use different thresholds (ICAO uses 1,500 km as a breakpoint for domestic). We use 3,700 km for DEFRA consistency.

### What our sample data looks like and why

Our sample `concur_expense_export_Jan2024.csv` has four rows:
1. DEL→BOM economy flight — short-haul domestic, distance computed from IATA codes (testing haversine)
2. BOM→LHR business class — long-haul international, business class factor (testing cabin class differentiation — business is 2.5x economy on this route)
3. Hotel stay, 2 nights, Marriott — testing hotel room-night calculation
4. Ola cab, no distance given, amount provided — testing the amount-to-distance heuristic (₹15/km fallback)

We deliberately included the Ola row without a distance to demonstrate the heuristic and the warning it generates. In practice, ~40% of ground transport rows in Indian expense reports lack distance data.

We also included business class on the London flight because that's a common source of significant underreporting — many tools default everything to economy.

### What would break in a real deployment

1. **Unknown airports:** Our database has ~150 major airports. A DEL→IXU (Aurangabad) flight would fail because IXU is not in our database. In production, we'd load the full OurAirports.com dataset (~7,000 airports with coordinates).

2. **Multi-leg trips:** Concur often exports each flight segment as a separate row (DEL→DXB, DXB→LHR are two rows for one journey). Our system treats them independently, which is correct — each leg has its own emission. But if the client exports trip-level summaries instead of segment-level, we'd need different parsing logic.

3. **CO2 reported by platform vs our calculation:** Concur and Navan sometimes pre-calculate CO2. Their methodology may differ (ICAO vs DEFRA, RF included or not). We flag discrepancies >30% but don't resolve them — an analyst must decide which number to use.

4. **Hotel star rating / chain:** DEFRA 2023 has a single average hotel factor (20.8 kg CO2e/room-night). In reality, a 5-star hotel has a much higher footprint than a budget hotel. Without hotel-specific data (which is rarely in expense exports), we use the average and accept the uncertainty.

5. **Personal vehicles and mileage claims:** Employees using personal cars for business claim mileage reimbursement. The expense export shows amount (₹/km rate × km), but emission factor depends on the employee's actual vehicle (petrol sedan vs diesel SUV vs EV). We use an average car factor and flag it. Some clients exclude personal vehicle mileage from Scope 3 entirely.

6. **Domestic rail not well covered:** Concur doesn't always distinguish between long-distance train (Indian Railways) and metro/subway. Indian Railways has a much lower emission factor than the DEFRA UK national rail figure we use. We apply DEFRA rail as a proxy but this significantly overestimates Indian Railways emissions (the Indian grid is still coal-heavy but rail electrification and efficiency differ significantly from UK).
