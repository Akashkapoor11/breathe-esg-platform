"""
Utility Parser — Electricity portal CSV export

Research rationale (see SOURCES.md):
  Most enterprise clients receive electricity bills either as PDFs or
  via a web portal that offers CSV/Excel export. PDF parsing (OCR or
  native text extraction) has high failure rates for multi-column bill
  layouts with varying templates across DISCOMs.

  Portal CSV is chosen because:
  1. All major Indian DISCOMs (TATA Power, MSEDCL, BSES, BESCOM, TNEB)
     offer account portal CSV download.
  2. The schema is more stable than PDFs — changes are versioned.
  3. API availability is patchy; Green Button (US standard) has no Indian
     equivalent, and DISCOM APIs are not publicly documented.

  Key edge case handled: billing periods often do NOT align with calendar
  months. A MSEDCL bill might run from Jan 7 to Feb 6. We store the
  actual period_start / period_end rather than forcing a calendar month,
  and flag bills with periods > 45 days or < 20 days as suspicious.
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional

from apps.ingestion.emission_factors import (
    INDIA_GRID_FACTOR, INDIA_GRID_FACTOR_SOURCE, ELECTRICITY_UNIT_MAP
)


# Expected column names (case-insensitive, partial match allowed)
COLUMN_ALIASES = {
    'account_number':    ['account_number', 'account number', 'acc_no', 'account no', 'acct'],
    'meter_id':          ['meter_id', 'meter id', 'meter_number', 'meter no', 'metering point'],
    'service_address':   ['service_address', 'service address', 'address', 'location', 'site'],
    'period_start':      ['billing_period_start', 'period_start', 'bill_from', 'from_date', 'start_date', 'period from'],
    'period_end':        ['billing_period_end', 'period_end', 'bill_to', 'to_date', 'end_date', 'period to'],
    'usage':             ['usage_kwh', 'usage', 'consumption', 'units_consumed', 'energy_kwh', 'kwh', 'units'],
    'usage_unit':        ['usage_unit', 'unit', 'uom'],
    'peak_demand':       ['peak_demand_kw', 'peak_demand', 'demand_kw', 'max_demand', 'contracted_demand'],
    'rate_schedule':     ['rate_schedule', 'tariff', 'tariff_code', 'rate_code', 'tariff category'],
    'total_charges':     ['total_charges', 'total_amount', 'bill_amount', 'amount', 'invoice_amount'],
    'currency':          ['currency', 'curr'],
}

DATE_FORMATS = [
    '%Y-%m-%d',     # ISO 8601 (most portal exports)
    '%d-%m-%Y',     # Indian DD-MM-YYYY
    '%d/%m/%Y',
    '%m/%d/%Y',
    '%d.%m.%Y',     # European
    '%B %d, %Y',    # "January 07, 2024"
    '%d %b %Y',     # "07 Jan 2024"
]


def parse_date(s: str) -> Optional[date]:
    s = str(s).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_decimal(s: str) -> Optional[Decimal]:
    s = str(s).strip().replace(',', '').replace('\xa0', '')
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def find_column(headers: List[str], aliases: List[str]) -> Optional[str]:
    """Find the first header that matches any alias (case-insensitive)."""
    headers_lower = {h.lower().strip(): h for h in headers}
    for alias in aliases:
        if alias in headers_lower:
            return headers_lower[alias]
    return None


def build_column_map(headers: List[str]) -> dict:
    """Map canonical keys → actual header string."""
    result = {}
    for canon, aliases in COLUMN_ALIASES.items():
        h = find_column(headers, aliases)
        if h:
            result[canon] = h
    return result


def normalize_usage(value: Decimal, unit_str: str) -> Tuple[Decimal, str, List[str]]:
    warnings = []
    unit_lower = unit_str.strip().lower().replace(' ', '')
    mapping = ELECTRICITY_UNIT_MAP.get(unit_lower)

    if mapping is None:
        warnings.append(
            f"Unknown electricity unit '{unit_str}' — assumed kWh. Verify with source."
        )
        return value, 'kWh', warnings

    factor, std_unit = mapping
    if factor != Decimal('1'):
        warnings.append(f"Usage converted from {unit_str} to kWh (×{factor})")
    return value * factor, std_unit, warnings


def parse_utility_csv(
    file_bytes: bytes, org
) -> Tuple[List[dict], List[dict]]:
    """
    Parse a utility portal CSV export.
    Returns (records, log_entries).

    One row in the CSV = one billing period for one meter.
    Multiple meters at one facility appear as separate rows.
    """
    try:
        text = file_bytes.decode('utf-8-sig')  # handle BOM from Excel exports
    except UnicodeDecodeError:
        text = file_bytes.decode('latin-1', errors='replace')

    # Detect delimiter
    sample = text[:1000]
    delimiter = ';' if sample.count(';') > sample.count(',') else ','

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = reader.fieldnames or []
    col_map = build_column_map(headers)

    records = []
    log = []

    # Emit a warning if key columns are missing
    required = ['period_start', 'period_end', 'usage']
    for req in required:
        if req not in col_map:
            log.append({
                'level': 'warning', 'row': 0,
                'message': f"Expected column '{req}' not found — check file format"
            })

    # Use org's custom factor if set, else India grid default
    ef = Decimal(str(org.electricity_emission_factor)) if org else INDIA_GRID_FACTOR
    ef_source = (
        str(org.electricity_factor_source)
        if org and org.electricity_factor_source
        else INDIA_GRID_FACTOR_SOURCE
    )

    for row_idx, row in enumerate(reader, start=2):
        raw_copy = dict(row)

        def get(key):
            col = col_map.get(key)
            return row.get(col, '').strip() if col else ''

        # ── Usage ─────────────────────────────────────────────────────────
        usage_str = get('usage')
        usage = parse_decimal(usage_str)
        if usage is None or usage <= 0:
            log.append({'level': 'error', 'row': row_idx,
                        'message': f"Invalid usage value '{usage_str}' — row skipped"})
            continue

        unit_str = get('usage_unit') or 'kWh'
        usage_norm, unit_norm, unit_warnings = normalize_usage(usage, unit_str)
        warnings = list(unit_warnings)

        # ── Dates ─────────────────────────────────────────────────────────
        period_start = parse_date(get('period_start'))
        period_end = parse_date(get('period_end'))

        if period_start is None or period_end is None:
            log.append({'level': 'error', 'row': row_idx,
                        'message': f"Cannot parse billing period dates — row skipped"})
            continue

        if period_end < period_start:
            log.append({'level': 'error', 'row': row_idx,
                        'message': "period_end before period_start — row skipped"})
            continue

        period_days = (period_end - period_start).days + 1
        if period_days > 45:
            warnings.append(
                f"Billing period is {period_days} days (> 45). "
                "May be a catch-up bill or data error."
            )
        if period_days < 20:
            warnings.append(
                f"Billing period is only {period_days} days (< 20). "
                "Possible partial bill or meter replacement."
            )

        # ── Identifiers ───────────────────────────────────────────────────
        meter_id = get('meter_id') or 'UNKNOWN'
        account = get('account_number') or ''
        address = get('service_address') or ''
        rate_schedule = get('rate_schedule') or ''

        # ── Emission calculation ──────────────────────────────────────────
        co2e_kg = usage_norm * ef

        # Large consumption flag (>1 GWh in a single billing period)
        if usage_norm > Decimal('1000000'):
            warnings.append(
                f"Unusually large consumption: {usage_norm:,.0f} kWh. "
                "Verify this isn't an MWh/GWh unit error."
            )

        source_ref = f"Meter: {meter_id}"
        if account:
            source_ref += f" | Account: {account}"

        activity_desc = f"Electricity consumption"
        if address:
            activity_desc += f" at {address}"
        if rate_schedule:
            activity_desc += f" ({rate_schedule})"

        records.append({
            'scope': 2,
            'category': 'purchased_electricity',
            'activity_description': activity_desc,
            'activity_value': float(usage),
            'activity_unit': unit_str or 'kWh',
            'activity_value_normalized': float(usage_norm),
            'activity_unit_normalized': 'kWh',
            'emission_factor': float(ef),
            'emission_factor_unit': 'kg CO2e/kWh',
            'emission_factor_source': ef_source,
            'co2e_kg': float(co2e_kg),
            'period_start': period_start,
            'period_end': period_end,
            'source_ref': source_ref,
            'raw_data': raw_copy,
            'warnings': warnings,
        })

        if warnings:
            log.append({'level': 'warning', 'row': row_idx,
                        'message': '; '.join(warnings)})

    return records, log
