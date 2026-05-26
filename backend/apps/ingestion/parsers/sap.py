"""
SAP Parser — ALV CSV flat file format

Research rationale (see SOURCES.md for full writeup):
  We chose the ALV CSV export (Report → List → Save as spreadsheet).
  This is by far the most common way SAP data leaves enterprise clients:
  sustainability teams ask the SAP team to run a standard MM report
  (ME2M, ME80FN, or a custom ZMM_ transaction) and export the ALV grid.

  We intentionally did NOT choose IDoc or OData:
    - IDoc requires a configured EDI partner profile; rarely set up for
      internal reporting extracts.
    - OData/API (S/4 HANA Fiori) is only available on newer S/4 clients;
      legacy ECC 6.0 (still >60% of installed base) doesn't have it.

Column mapping handles both English and German SAP field labels,
since German ALV headers are common when the system language is DE.
"""

import csv
import io
import chardet
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import List, Dict, Tuple, Optional

from apps.ingestion.emission_factors import (
    FUEL_FACTORS, FUEL_KEYWORD_MAP, SAP_UNIT_MAP
)


# ── Column header mapping ─────────────────────────────────────────────────────
# SAP field name (DDIC name or ALV label) → our canonical key
# German labels included for systems running DE system language
COLUMN_MAP = {
    # Document / PO
    'ebeln': 'po_number',           # Purchase Order Number
    'belnr': 'doc_number',          # Document Number (alternative)
    'ebelp': 'line_item',           # PO line item
    # Dates
    'bldat': 'document_date',       # Document Date
    'budat': 'posting_date',        # Posting Date (Buchungsdatum)
    'aedat': 'document_date',       # Change date (alternative)
    # Org units
    'bukrs': 'company_code',        # Company Code (Buchungskreis)
    'werks': 'plant',               # Plant (Werk)
    'lgort': 'storage_location',    # Storage Location
    'kostl': 'cost_center',         # Cost Center (Kostenstelle)
    # Material
    'matnr': 'material_number',
    'maktx': 'material_description',# Material Short Text (often German)
    'maktg': 'material_description',# Material long text (alternative label)
    # Quantity
    'menge': 'quantity',            # Quantity (Menge)
    'meins': 'unit',                # Base Unit of Measure (Mengeneinheit)
    'erfmg': 'quantity',            # Entry Quantity (alternative)
    'erfme': 'unit',                # Entry Unit (alternative)
    # Value
    'netpr': 'net_price',           # Net Price
    'netwr': 'net_value',           # Net Value
    'waers': 'currency',            # Currency (Währung)
    # Text
    'bktxt': 'item_text',           # Document Header Text
    'txz01': 'item_text',           # Short Text (alternative)
    # English-label variants (what you get when SY-LANGU = EN)
    'purchase order': 'po_number',
    'document number': 'doc_number',
    'plant': 'plant',
    'company code': 'company_code',
    'cost center': 'cost_center',
    'material': 'material_number',
    'material description': 'material_description',
    'quantity': 'quantity',
    'unit': 'unit',
    'net price': 'net_price',
    'net value': 'net_value',
    'currency': 'currency',
    'document date': 'document_date',
    'posting date': 'posting_date',
    'text': 'item_text',
}

# SAP plant code → human-readable location
# In a real deployment this comes from a lookup table / T001W; we hardcode for demo
PLANT_LOOKUP = {
    'PLNT_DEL': 'Delhi Plant',
    'PLNT_MUM': 'Mumbai Plant',
    'PLNT_BNG': 'Bangalore Plant',
    'PLNT_CHN': 'Chennai Plant',
    'PLNT_HYD': 'Hyderabad Plant',
    '1000': 'Main Plant (Hamburg)',   # common SAP default
    '1100': 'Plant Berlin',
    '2000': 'Plant Mumbai',
    '3000': 'Plant Delhi',
}

SAP_DATE_FORMATS = [
    '%Y%m%d',       # YYYYMMDD (SAP internal)
    '%d.%m.%Y',     # DD.MM.YYYY (German locale)
    '%m/%d/%Y',     # MM/DD/YYYY (EN-US)
    '%d/%m/%Y',     # DD/MM/YYYY (EN-IN)
    '%Y-%m-%d',     # ISO
]


def parse_sap_date(s: str) -> Optional[date]:
    s = str(s).strip()
    for fmt in SAP_DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_quantity(s: str) -> Optional[Decimal]:
    """SAP may use comma as decimal separator (German locale)."""
    s = str(s).strip().replace('\xa0', '').replace(' ', '')
    # European format: 1.234,56 → strip dots as thousands, replace comma as decimal
    if ',' in s and '.' in s:
        if s.index('.') < s.index(','):
            # 1.234,56 pattern
            s = s.replace('.', '').replace(',', '.')
        else:
            # 1,234.56 pattern
            s = s.replace(',', '')
    elif ',' in s and '.' not in s:
        s = s.replace(',', '.')
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def detect_encoding(raw_bytes: bytes) -> str:
    result = chardet.detect(raw_bytes)
    enc = result.get('encoding') or 'utf-8'
    # SAP often exports in ISO-8859-1 (Latin-1) or Windows-1252
    if enc.lower() in ('iso-8859-1', 'latin-1', 'windows-1252'):
        return 'cp1252'
    return enc


def normalize_header(h: str) -> str:
    return h.strip().lower().replace(' ', '_').replace('-', '_').replace('/', '_')


def map_columns(raw_headers: List[str]) -> Dict[str, str]:
    """
    Returns mapping: raw_header → canonical_key.
    Unknown columns are kept as-is (may be useful in raw_data).
    """
    mapping = {}
    for h in raw_headers:
        norm = normalize_header(h)
        # Try exact match first (field code like WERKS), then English phrase
        canonical = COLUMN_MAP.get(norm) or COLUMN_MAP.get(h.strip().lower())
        mapping[h] = canonical or h
    return mapping


def identify_fuel_type(material_desc: str, material_number: str) -> Optional[str]:
    """
    Match material description against known fuel keywords.
    Material number patterns (MAT-DIESEL, etc.) also tried.
    Returns fuel type key or None if no match (procurement, not fuel).
    """
    text = (material_desc + ' ' + material_number).lower()
    for keyword, fuel_type in FUEL_KEYWORD_MAP.items():
        if keyword in text:
            return fuel_type
    return None


def normalize_quantity_and_unit(
    qty: Decimal, unit_raw: str
) -> Tuple[Optional[Decimal], str, list]:
    """
    Convert quantity to standard unit for the fuel type.
    Returns (normalized_qty, standard_unit, warnings).
    """
    warnings = []
    unit_clean = unit_raw.strip().upper()
    mapping = SAP_UNIT_MAP.get(unit_clean)

    if mapping is None:
        warnings.append(
            f"Unknown SAP unit '{unit_raw}' — quantity left as-is, unit flagged for review"
        )
        return qty, unit_raw, warnings

    std_unit, factor = mapping

    if factor is None:
        # KG case: need density to convert to volume; flag it
        warnings.append(
            f"Unit is KG — cannot convert to volume without fuel density. "
            f"Quantity ({qty} kg) left as-is; review required."
        )
        return qty, 'kg', warnings

    normalized = qty * factor
    if factor != Decimal('1'):
        warnings.append(f"Unit converted from {unit_raw} to {std_unit} (factor: {factor})")

    return normalized, std_unit, warnings


def parse_sap_csv(file_bytes: bytes, org) -> Tuple[List[dict], List[dict]]:
    """
    Parse an SAP ALV CSV export.
    Returns (records, log_entries).

    records: list of dicts ready to create EmissionRecord objects.
    log_entries: list of {level, row, message} for IngestionJob.processing_log.
    """
    encoding = detect_encoding(file_bytes)
    text = file_bytes.decode(encoding, errors='replace')

    # SAP sometimes exports with semicolons (German locale) or commas
    sample = text[:2000]
    delimiter = ';' if sample.count(';') > sample.count(',') else ','

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    raw_headers = reader.fieldnames or []
    col_map = map_columns(raw_headers)

    records = []
    log = []

    for row_idx, row in enumerate(reader, start=2):  # row 1 = header
        # Remap columns
        mapped = {col_map.get(k, k): v for k, v in row.items()}
        raw_copy = dict(row)

        # ── Extract key fields ────────────────────────────────────────────
        qty_raw = mapped.get('quantity', '').strip()
        unit_raw = mapped.get('unit', '').strip()
        mat_desc = mapped.get('material_description', '').strip()
        mat_num = mapped.get('material_number', '').strip()
        plant_raw = mapped.get('plant', '').strip()
        doc_date_raw = mapped.get('document_date', mapped.get('posting_date', '')).strip()
        post_date_raw = mapped.get('posting_date', doc_date_raw).strip()
        doc_number = (
            mapped.get('po_number') or mapped.get('doc_number') or ''
        ).strip()
        cost_center = mapped.get('cost_center', '').strip()

        # Skip empty rows
        if not qty_raw and not mat_desc:
            continue

        # ── Validate quantity ─────────────────────────────────────────────
        qty = parse_quantity(qty_raw)
        if qty is None:
            log.append({'level': 'error', 'row': row_idx,
                        'message': f"Cannot parse quantity '{qty_raw}' — row skipped"})
            continue
        if qty <= 0:
            log.append({'level': 'warning', 'row': row_idx,
                        'message': f"Quantity is {qty} (zero or negative) — row skipped"})
            continue

        # ── Identify as fuel ──────────────────────────────────────────────
        fuel_type = identify_fuel_type(mat_desc, mat_num)
        if fuel_type is None:
            log.append({'level': 'info', 'row': row_idx,
                        'message': f"'{mat_desc}' not identified as fuel — skipped (non-fuel procurement)"})
            continue

        # ── Parse dates ───────────────────────────────────────────────────
        doc_date = parse_sap_date(doc_date_raw)
        post_date = parse_sap_date(post_date_raw) if post_date_raw else doc_date

        if doc_date is None:
            log.append({'level': 'warning', 'row': row_idx,
                        'message': f"Cannot parse date '{doc_date_raw}' — defaulting to posting date"})
            doc_date = post_date

        if doc_date is None:
            log.append({'level': 'error', 'row': row_idx,
                        'message': "No valid date found — row skipped"})
            continue

        # ── Normalize quantity & unit ──────────────────────────────────────
        qty_norm, unit_norm, unit_warnings = normalize_quantity_and_unit(qty, unit_raw)
        warnings = list(unit_warnings)

        # For gas, unit is m³ not L — handle separately
        if fuel_type in ('natural_gas', 'erdgas') and unit_norm == 'L':
            warnings.append("Natural gas quantity interpreted as m³ despite L unit code — verify with source")
            unit_norm = 'm³'

        # ── Emission factor ───────────────────────────────────────────────
        factor, factor_source = FUEL_FACTORS[fuel_type]
        co2e_kg = qty_norm * factor

        # ── Category (Scope 1) ────────────────────────────────────────────
        # Fuel purchased for vehicles → mobile combustion (Scope 1, Cat mobile)
        # Fuel for boilers/generators → stationary combustion (Scope 1, Cat stationary)
        # We infer from material description; fleet/vehicle keywords → mobile
        is_mobile = any(k in (mat_desc + cost_center).lower()
                        for k in ('vehicle', 'fleet', 'truck', 'lorry', 'car', 'van', 'fuel'))
        category = 'mobile_combustion' if is_mobile else 'stationary_combustion'

        plant_label = PLANT_LOOKUP.get(plant_raw, plant_raw or 'Unknown Plant')

        if not plant_raw:
            warnings.append("No plant code in source — location unknown")

        # ── High-volume flag ──────────────────────────────────────────────
        if qty_norm > Decimal('50000'):
            warnings.append(
                f"Unusually large quantity: {qty_norm} {unit_norm}. "
                "Verify this isn't a sum row or data entry error."
            )

        records.append({
            'scope': 1,
            'category': category,
            'activity_description': (
                f"{mat_desc or fuel_type.replace('_', ' ').title()} "
                f"at {plant_label}"
            ),
            'activity_value': float(qty),
            'activity_unit': unit_raw,
            'activity_value_normalized': float(qty_norm),
            'activity_unit_normalized': unit_norm,
            'emission_factor': float(factor),
            'emission_factor_unit': f'kg CO2e/{unit_norm}',
            'emission_factor_source': factor_source,
            'co2e_kg': float(co2e_kg),
            'period_start': doc_date,
            'period_end': post_date or doc_date,
            'source_ref': (
                f"SAP Doc: {doc_number} | Plant: {plant_raw} | "
                f"Material: {mat_num}"
            ),
            'raw_data': raw_copy,
            'warnings': warnings,
        })

        if warnings:
            log.append({'level': 'warning', 'row': row_idx,
                        'message': '; '.join(warnings)})

    return records, log
