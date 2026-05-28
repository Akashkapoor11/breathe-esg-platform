# Breathe ESG — Emissions Ingestion Platform

Django REST + React prototype for ingesting, normalizing, and reviewing corporate emissions data from SAP, utility portals, and corporate travel platforms.

## Live demo

> Deployed URL: https://breathe-esg-platform-kappa.vercel.app/login

**Credentials:**
- `admin / admin123` — full access, can lock records
- `analyst / analyst123` — review access (approve / reject / flag)

## Quick start (local)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

API runs at `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:5173`

## Project structure

```
breathe-esg/
├── backend/
│   ├── breathe_esg/        # Django project config (settings, urls, wsgi)
│   ├── apps/
│   │   ├── accounts/       # Organization, CustomUser models
│   │   └── ingestion/      # IngestionJob, EmissionRecord, AuditEvent
│   │       ├── parsers/
│   │       │   ├── sap.py      # SAP ALV CSV parser
│   │       │   ├── utility.py  # Utility portal CSV parser
│   │       │   └── travel.py   # Concur/Navan CSV parser
│   │       ├── emission_factors.py  # DEFRA 2023 + CEA factors
│   │       └── management/commands/seed_demo.py
│   └── apps/sample_data/   # Example CSVs matching parser expectations
├── frontend/
│   └── src/
│       ├── pages/          # Dashboard, Records, RecordDetail, Upload, Jobs
│       ├── components/     # Layout, sidebar
│       └── api/client.js   # API wrapper
└── docs/
    ├── MODEL.md      # Data model design (35% of grade)
    ├── DECISIONS.md  # Every ambiguity resolved
    ├── TRADEOFFS.md  # Three things deliberately not built
    └── SOURCES.md    # Research notes on each data source
```

## Sample CSV formats

Download from `backend/apps/sample_data/`:

| File | Source |
|---|---|
| `MM_fuel_procurement_Jan2024.csv` | SAP ALV export (German material names, mixed units) |
| `electricity_Q1_2024_all_sites.csv` | DISCOM portal CSV (non-calendar billing periods) |
| `concur_expense_export_Jan2024.csv` | Concur expense report (IATA codes, missing distances) |

## API endpoints

```
POST /api/auth/login/               → JWT token pair
POST /api/jobs/upload/              → Ingest a file
GET  /api/jobs/                     → List ingestion jobs
GET  /api/records/                  → List emission records (filterable)
GET  /api/records/{id}/             → Record detail + audit trail
POST /api/records/{id}/review/      → Approve / reject / flag
POST /api/records/bulk-review/      → Bulk review action
GET  /api/records/export/           → CSV export of approved records
GET  /api/stats/                    → Dashboard statistics
```

## Grading documentation

All four required documents are in `docs/`:

- **MODEL.md** — Data model, multi-tenancy, Scope 1/2/3 categorization, source-of-truth tracking, unit normalization, audit trail
- **DECISIONS.md** — Format choices, subset decisions, questions for the PM
- **TRADEOFFS.md** — Three deliberate omissions with reasoning
- **SOURCES.md** — Research on each real-world data format
