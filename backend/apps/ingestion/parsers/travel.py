"""
Travel Parser — Concur/Navan expense report CSV export

Research rationale (see SOURCES.md):
  Concur (SAP Concur) exposes a Reporting API that returns travel data
  as JSON, but this requires OAuth2 tokens issued per-company — not
  practical for a prototype without client credentials.

  The CSV export is chosen because:
  1. Concur's "Expense Report" export CSV is a standard product feature,
     no API tokens required.
  2. Navan exports in a similar columnar format.
  3. Travel managers already run these reports for expense reconciliation,
     so the data flow exists.

  Key challenges handled:
  - Distances are often NOT in the export (especially for flights).
    We compute great-circle distance from IATA airport codes using haversine.
  - Cabin class is sometimes missing; we flag and use economy as conservative default.
  - Ground transport doesn't always have distance; we use cost/rate heuristic where available.
  - Hotel rows have no distance — we use room-nights × factor.

  IATA airport coordinate database: built-in subset of ~150 major airports.
  In production, this would be replaced with the full OurAirports.com dataset.
"""

import csv
import io
import math
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import List, Tuple, Optional

from apps.ingestion.emission_factors import (
    AIR_FACTORS, HOTEL_FACTOR, HOTEL_FACTOR_SOURCE,
    GROUND_FACTORS, SHORT_HAUL_KM_THRESHOLD
)


# ── Airport coordinates (IATA code → (lat, lon)) ─────────────────────────────
# Subset of major airports. Full deployment would load OurAirports.com dataset.
AIRPORT_COORDS = {
    # India
    'DEL': (28.5665, 77.1031),   # Indira Gandhi, Delhi
    'BOM': (19.0896, 72.8656),   # Chhatrapati Shivaji, Mumbai
    'BLR': (13.1986, 77.7066),   # Kempegowda, Bangalore
    'MAA': (12.9941, 80.1709),   # Chennai
    'HYD': (17.2313, 78.4298),   # Rajiv Gandhi, Hyderabad
    'CCU': (22.6520, 88.4467),   # Netaji Subhas, Kolkata
    'COK': (10.1520, 76.4019),   # Cochin
    'PNQ': (18.5822, 73.9197),   # Pune
    'AMD': (23.0772, 72.6347),   # Ahmedabad
    'IXC': (30.6735, 76.7885),   # Chandigarh
    # Asia
    'SIN': (1.3644, 103.9915),   # Changi, Singapore
    'DXB': (25.2532, 55.3657),   # Dubai
    'BKK': (13.6811, 100.7472),  # Bangkok Suvarnabhumi
    'KUL': (2.7456, 101.7072),   # Kuala Lumpur
    'HKG': (22.3080, 113.9185),  # Hong Kong
    'NRT': (35.7720, 140.3929),  # Tokyo Narita
    'ICN': (37.4602, 126.4407),  # Seoul Incheon
    'PEK': (40.0799, 116.6031),  # Beijing Capital
    'PVG': (31.1443, 121.8083),  # Shanghai Pudong
    # Europe
    'LHR': (51.4775, -0.4614),   # London Heathrow
    'CDG': (49.0097, 2.5479),    # Paris Charles de Gaulle
    'FRA': (50.0379, 8.5622),    # Frankfurt
    'AMS': (52.3086, 4.7639),    # Amsterdam Schiphol
    'ZRH': (47.4647, 8.5492),    # Zurich
    'MUC': (48.3538, 11.7861),   # Munich
    # Americas
    'JFK': (40.6413, -73.7781),  # New York JFK
    'EWR': (40.6895, -74.1745),  # New York Newark
    'LAX': (33.9425, -118.4081), # Los Angeles
    'SFO': (37.6213, -122.3790), # San Francisco
    'ORD': (41.9742, -87.9073),  # Chicago O'Hare
    'IAD': (38.9531, -77.4565),  # Washington Dulles
    'YYZ': (43.6772, -79.6306),  # Toronto
    # Middle East & Africa
    'AUH': (24.4330, 54.6511),   # Abu Dhabi
    'DOH': (25.2731, 51.6081),   # Doha
    'JNB': (-26.1367, 28.2411),  # Johannesburg
    'NBO': (-1.3192, 36.9275),   # Nairobi
}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km between two points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def airport_distance_km(origin: str, destination: str) -> Tuple[Optional[float], List[str]]:
    """
    Compute flight distance from IATA codes.
    Returns (distance_km, warnings).
    """
    warnings = []
    o = origin.strip().upper()
    d = destination.strip().upper()

    coords_o = AIRPORT_COORDS.get(o)
    coords_d = AIRPORT_COORDS.get(d)

    if not coords_o:
        warnings.append(f"Airport '{o}' not in local database — distance cannot be computed")
        return None, warnings
    if not coords_d:
        warnings.append(f"Airport '{d}' not in local database — distance cannot be computed")
        return None, warnings

    dist = haversine_km(coords_o[0], coords_o[1], coords_d[0], coords_d[1])
    warnings.append(
        f"Distance {o}→{d} computed via haversine ({dist:.0f} km). "
        "Verify against actual flight path (haversine ≈ great-circle, not routing)."
    )
    return dist, warnings


def normalize_cabin_class(raw: str) -> str:
    raw = raw.strip().lower()
    if any(k in raw for k in ('economy', 'eco', 'y class', 'coach')):
        return 'economy'
    if any(k in raw for k in ('premium economy', 'premium_economy', 'prem eco', 'w class')):
        return 'premium_economy'
    if any(k in raw for k in ('business', 'biz', 'c class', 'j class')):
        return 'business'
    if any(k in raw for k in ('first', 'f class', 'a class')):
        return 'first'
    return 'economy'  # default conservative


def normalize_travel_type(raw: str) -> str:
    raw = raw.strip().upper()
    if raw in ('FLIGHT', 'AIR', 'AIRLINE', 'FLT'):
        return 'flight'
    if raw in ('HOTEL', 'LODGING', 'ACCOMMODATION', 'HTL'):
        return 'hotel'
    if raw in ('CAR', 'RENTAL', 'TAXI', 'OLA', 'UBER', 'AUTO', 'GRD', 'GROUND', 'CAB'):
        return 'ground'
    if raw in ('RAIL', 'TRAIN', 'METRO', 'SUBWAY'):
        return 'rail'
    return 'unknown'


def parse_date(s: str) -> Optional[date]:
    s = str(s).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d %b %Y', '%b %d, %Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_decimal(s: str) -> Optional[Decimal]:
    if not s:
        return None
    s = str(s).strip().replace(',', '').replace('\xa0', '')
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


COLUMN_ALIASES = {
    'trip_id':      ['trip_id', 'trip id', 'report_id', 'report id', 'expense_id', 'expense id'],
    'employee_id':  ['employee_id', 'employee id', 'emp_id', 'emp id', 'user_id', 'user id'],
    'department':   ['department', 'dept', 'cost_center', 'cost center'],
    'travel_date':  ['travel_date', 'travel date', 'departure_date', 'departure date', 'date'],
    'type':         ['type', 'expense_type', 'expense type', 'travel_type', 'segment_type', 'category'],
    'origin':       ['origin', 'from', 'departure', 'origin_airport', 'origin airport'],
    'destination':  ['destination', 'to', 'arrival', 'dest', 'destination_airport'],
    'class':        ['class', 'cabin_class', 'cabin class', 'service_class', 'ticket_class'],
    'nights':       ['nights', 'num_nights', 'number_of_nights', 'room_nights'],
    'distance_km':  ['distance_km', 'distance km', 'distance', 'miles', 'dist_km'],
    'amount':       ['amount', 'amount_inr', 'total_amount', 'cost', 'expense_amount'],
    'currency':     ['currency', 'curr'],
    'vendor':       ['vendor', 'airline', 'hotel_name', 'provider', 'supplier'],
    'co2_reported': ['co2', 'co2_reported', 'co2_grams', 'carbon', 'co2e_g', 'reported_co2'],
}


def find_col(headers: List[str], aliases: List[str]) -> Optional[str]:
    h_lower = {h.lower().strip(): h for h in headers}
    for a in aliases:
        if a in h_lower:
            return h_lower[a]
    return None


def parse_travel_csv(
    file_bytes: bytes, org
) -> Tuple[List[dict], List[dict]]:
    try:
        text = file_bytes.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = file_bytes.decode('latin-1', errors='replace')

    sample = text[:1000]
    delimiter = ';' if sample.count(';') > sample.count(',') else ','

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = reader.fieldnames or []

    col_map = {k: find_col(headers, v) for k, v in COLUMN_ALIASES.items()}

    records = []
    log = []

    for row_idx, row in enumerate(reader, start=2):
        raw_copy = dict(row)

        def get(key, default=''):
            col = col_map.get(key)
            return row.get(col, default).strip() if col else default

        travel_type_raw = get('type')
        travel_type = normalize_travel_type(travel_type_raw)

        if travel_type == 'unknown':
            log.append({'level': 'warning', 'row': row_idx,
                        'message': f"Unrecognised travel type '{travel_type_raw}' — row skipped"})
            continue

        trip_id = get('trip_id') or f'ROW-{row_idx}'
        employee_id = get('employee_id')
        department = get('department')
        vendor = get('vendor')

        date_val = parse_date(get('travel_date'))
        if date_val is None:
            log.append({'level': 'error', 'row': row_idx,
                        'message': f"Cannot parse travel date — row skipped"})
            continue

        warnings = []
        record = None

        # ── Flight ────────────────────────────────────────────────────────
        if travel_type == 'flight':
            origin = get('origin').upper().strip()
            dest = get('destination').upper().strip()
            cabin_raw = get('class')
            cabin = normalize_cabin_class(cabin_raw)
            if not cabin_raw:
                warnings.append("Cabin class not specified — defaulting to economy (conservative)")

            # Distance: use column if provided, else compute from airport codes
            dist_str = get('distance_km')
            dist_km = parse_decimal(dist_str)

            if dist_km is None:
                if origin and dest:
                    dist_km_float, dist_warnings = airport_distance_km(origin, dest)
                    warnings.extend(dist_warnings)
                    dist_km = Decimal(str(dist_km_float)) if dist_km_float else None
                else:
                    warnings.append("No origin/destination airport codes — cannot compute distance")

            if dist_km is None:
                log.append({'level': 'error', 'row': row_idx,
                            'message': f"Trip {trip_id}: cannot determine flight distance — skipped"})
                continue

            haul = 'short' if dist_km < SHORT_HAUL_KM_THRESHOLD else 'long'

            # First class only available for long-haul in DEFRA
            if cabin == 'first' and haul == 'short':
                cabin = 'business'
                warnings.append("First class on short-haul not in DEFRA table — using business class factor")

            factor_key = (haul, cabin)
            if factor_key not in AIR_FACTORS:
                factor_key = (haul, 'economy')
                warnings.append(f"No factor for ({haul}, {cabin}) — using economy")

            ef, ef_source = AIR_FACTORS[factor_key]
            co2e_kg = dist_km * ef

            # Check against vendor-reported CO2 if present
            reported_co2_g = parse_decimal(get('co2_reported'))
            if reported_co2_g and reported_co2_g > 0:
                reported_kg = reported_co2_g / 1000
                diff_pct = abs(float(co2e_kg) - float(reported_kg)) / float(reported_kg) * 100
                if diff_pct > 30:
                    warnings.append(
                        f"Our calculation ({co2e_kg:.1f} kg CO2e) differs from "
                        f"vendor-reported ({reported_kg:.1f} kg CO2e) by {diff_pct:.0f}%. "
                        "Vendor may use different methodology (e.g., no RF multiplier)."
                    )

            record = {
                'scope': 3,
                'category': 'business_travel_air',
                'activity_description': (
                    f"Flight {origin}→{dest} "
                    f"({cabin.replace('_', ' ').title()}, {haul}-haul)"
                    + (f" via {vendor}" if vendor else "")
                ),
                'activity_value': float(dist_km),
                'activity_unit': 'km',
                'activity_value_normalized': float(dist_km),
                'activity_unit_normalized': 'km',
                'emission_factor': float(ef),
                'emission_factor_unit': 'kg CO2e/km',
                'emission_factor_source': ef_source,
                'co2e_kg': float(co2e_kg),
                'period_start': date_val,
                'period_end': date_val,
                'source_ref': (
                    f"Trip: {trip_id} | Emp: {employee_id} | "
                    f"{origin}→{dest}"
                ),
                'raw_data': raw_copy,
                'warnings': warnings,
            }

        # ── Hotel ─────────────────────────────────────────────────────────
        elif travel_type == 'hotel':
            nights_str = get('nights')
            nights = parse_decimal(nights_str)
            if nights is None or nights <= 0:
                log.append({'level': 'error', 'row': row_idx,
                            'message': f"Hotel row {trip_id}: invalid nights '{nights_str}' — skipped"})
                continue

            co2e_kg = nights * HOTEL_FACTOR

            record = {
                'scope': 3,
                'category': 'business_travel_hotel',
                'activity_description': (
                    f"Hotel stay {int(nights)} night(s)"
                    + (f" at {vendor}" if vendor else "")
                ),
                'activity_value': float(nights),
                'activity_unit': 'nights',
                'activity_value_normalized': float(nights),
                'activity_unit_normalized': 'nights',
                'emission_factor': float(HOTEL_FACTOR),
                'emission_factor_unit': 'kg CO2e/room-night',
                'emission_factor_source': HOTEL_FACTOR_SOURCE,
                'co2e_kg': float(co2e_kg),
                'period_start': date_val,
                'period_end': date_val,
                'source_ref': f"Trip: {trip_id} | Emp: {employee_id}",
                'raw_data': raw_copy,
                'warnings': warnings,
            }

        # ── Ground transport ──────────────────────────────────────────────
        elif travel_type in ('ground', 'rail'):
            dist_str = get('distance_km')
            dist_km = parse_decimal(dist_str)

            # Estimate distance from amount if not given
            if dist_km is None:
                amount = parse_decimal(get('amount'))
                if amount and amount > 0:
                    # Rough heuristic: ₹15/km is a typical auto/cab rate in India
                    dist_km = amount / Decimal('15')
                    warnings.append(
                        f"Distance not given — estimated from amount ÷ ₹15/km heuristic "
                        f"({dist_km:.1f} km). Significant uncertainty."
                    )
                else:
                    log.append({'level': 'error', 'row': row_idx,
                                'message': f"Ground trip {trip_id}: no distance or amount — skipped"})
                    continue

            vendor_key = vendor.lower() if vendor else 'default'
            ef, ef_source = GROUND_FACTORS.get(vendor_key, GROUND_FACTORS['default'])

            category = 'business_travel_rail' if travel_type == 'rail' else 'business_travel_ground'
            if travel_type == 'rail':
                ef, ef_source = GROUND_FACTORS['rail']

            co2e_kg = dist_km * ef

            record = {
                'scope': 3,
                'category': category,
                'activity_description': (
                    f"{'Rail' if travel_type == 'rail' else 'Ground transport'}"
                    + (f" via {vendor}" if vendor else "")
                    + f" ({dist_km:.1f} km)"
                ),
                'activity_value': float(dist_km),
                'activity_unit': 'km',
                'activity_value_normalized': float(dist_km),
                'activity_unit_normalized': 'km',
                'emission_factor': float(ef),
                'emission_factor_unit': 'kg CO2e/km',
                'emission_factor_source': ef_source,
                'co2e_kg': float(co2e_kg),
                'period_start': date_val,
                'period_end': date_val,
                'source_ref': f"Trip: {trip_id} | Emp: {employee_id}",
                'raw_data': raw_copy,
                'warnings': warnings,
            }

        if record:
            record['warnings'] = warnings
            records.append(record)
            if warnings:
                log.append({'level': 'warning', 'row': row_idx,
                            'message': '; '.join(warnings)})

    return records, log
