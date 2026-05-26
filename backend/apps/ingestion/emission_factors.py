"""
Emission factors used in Breathe ESG ingestion parsers.

All factors are in kg CO2e per unit of activity.

Sources cited explicitly so every audit trail can trace a number back
to a specific row in a published dataset.

Fuel factors: DEFRA 2023 Greenhouse Gas Reporting: Conversion Factors
  https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2023

Electricity factor: India CEA CO2 Baseline Database for the Indian Power Sector
  Version 18.0, FY 2022-23. Grid average: 0.716 kg CO2e/kWh

Travel factors: DEFRA 2023, Section: Business Travel (Air, Hotels, Cars)
  Short-haul: < 3700 km, Long-haul: >= 3700 km

Notes:
  - We use GWP100 from IPCC AR5 (CH4 = 28, N2O = 265).
  - We include CO2 + CH4 + N2O in all fuel combustion factors (as CO2e).
  - We do NOT include biogenic CO2 in diesel/petrol blends here;
    that would require knowing the blend percentage.
"""

from decimal import Decimal

# ── Fuel factors (kg CO2e per litre unless noted) ────────────────────────────
# Source: DEFRA 2023 Conversion Factors, Stationary Combustion, Table 1A
FUEL_FACTORS = {
    # key: (factor_kg_co2e_per_L, source_string)
    'diesel':       (Decimal('2.68737'), 'DEFRA 2023 Table 1A: Gas Oil/Diesel (kg CO2e/L)'),
    'petrol':       (Decimal('2.31420'), 'DEFRA 2023 Table 1A: Petrol (kg CO2e/L)'),
    'gasoline':     (Decimal('2.31420'), 'DEFRA 2023 Table 1A: Petrol (kg CO2e/L)'),
    'hsd':          (Decimal('2.68737'), 'DEFRA 2023 Table 1A: HSD (Diesel equivalent, kg CO2e/L)'),
    'lpg':          (Decimal('1.55490'), 'DEFRA 2023 Table 1A: LPG (kg CO2e/L)'),
    'furnace_oil':  (Decimal('3.17900'), 'DEFRA 2023 Table 1A: Fuel Oil (kg CO2e/L)'),
    # Natural gas: DEFRA 2023, unit kg CO2e per cubic metre (m³)
    'natural_gas':  (Decimal('2.04300'), 'DEFRA 2023 Table 1A: Natural Gas (kg CO2e/m³)'),
    'erdgas':       (Decimal('2.04300'), 'DEFRA 2023 Table 1A: Natural Gas (kg CO2e/m³)'),  # German
}

# Material description keyword → fuel type mapping
# SAP MAKTX (material description) is often German or abbreviated
FUEL_KEYWORD_MAP = {
    'diesel': 'diesel',
    'hsd': 'diesel',
    'high speed diesel': 'diesel',
    'gas oil': 'diesel',
    'petrol': 'petrol',
    'benzin': 'petrol',
    'gasoline': 'gasoline',
    'ms ': 'petrol',
    'motor spirit': 'petrol',
    'lpg': 'lpg',
    'flüssiggas': 'lpg',
    'natural gas': 'natural_gas',
    'erdgas': 'natural_gas',
    'lng': 'natural_gas',
    'cng': 'natural_gas',
    'furnace oil': 'furnace_oil',
    'heavy fuel': 'furnace_oil',
}

# SAP unit codes → standard unit
SAP_UNIT_MAP = {
    'L':    ('L', Decimal('1')),        # litre → litre
    'Ltr':  ('L', Decimal('1')),
    'LTR':  ('L', Decimal('1')),
    'KL':   ('L', Decimal('1000')),     # kilolitre → litre
    'KG':   ('L', None),               # kg — needs density; flagged
    'M3':   ('m³', Decimal('1')),       # cubic metre (for gas)
    'GAL':  ('L', Decimal('3.78541')),  # US gallon → litre
    'UGAL': ('L', Decimal('3.78541')),  # SAP US gallon code
    'GL':   ('L', Decimal('3.78541')),
}

# ── Electricity factor (kg CO2e per kWh) ────────────────────────────────────
# This is the location-based (grid average) factor for India.
# Per-org market-based factor is stored on the Organization model.
INDIA_GRID_FACTOR = Decimal('0.716000')
INDIA_GRID_FACTOR_SOURCE = (
    "CEA CO2 Baseline Database for the Indian Power Sector, "
    "Version 18.0, FY 2022-23, Grid Average (location-based)"
)

# Electricity unit normalization
ELECTRICITY_UNIT_MAP = {
    'kwh':  (Decimal('1'),      'kWh'),
    'mwh':  (Decimal('1000'),   'kWh'),
    'gwh':  (Decimal('1000000'),'kWh'),
    'units': (Decimal('1'),     'kWh'),  # "units" = kWh on Indian bills
}

# ── Travel factors (kg CO2e per passenger-km) ────────────────────────────────
# Source: DEFRA 2023 Conversion Factors, Business Travel — Air
# Short-haul: <3700 km radiative forcing included (multiplier ~1.891)
# Long-haul:  >=3700 km

AIR_FACTORS = {
    # (haul_type, cabin_class): (factor, source)
    ('short', 'economy'): (
        Decimal('0.25491'),
        'DEFRA 2023: Domestic/Short-haul economy, with RF (kg CO2e/pax-km)'
    ),
    ('short', 'premium_economy'): (
        Decimal('0.38237'),
        'DEFRA 2023: Short-haul premium economy, with RF (kg CO2e/pax-km)'
    ),
    ('short', 'business'): (
        Decimal('0.50982'),
        'DEFRA 2023: Short-haul business, with RF (kg CO2e/pax-km)'
    ),
    ('long', 'economy'): (
        Decimal('0.19521'),
        'DEFRA 2023: Long-haul economy, with RF (kg CO2e/pax-km)'
    ),
    ('long', 'premium_economy'): (
        Decimal('0.29282'),
        'DEFRA 2023: Long-haul premium economy, with RF (kg CO2e/pax-km)'
    ),
    ('long', 'business'): (
        Decimal('0.48802'),
        'DEFRA 2023: Long-haul business class, with RF (kg CO2e/pax-km)'
    ),
    ('long', 'first'): (
        Decimal('1.08898'),
        'DEFRA 2023: Long-haul first class, with RF (kg CO2e/pax-km)'
    ),
}

# Hotel: kg CO2e per room-night
HOTEL_FACTOR = Decimal('20.8000')
HOTEL_FACTOR_SOURCE = (
    'DEFRA 2023: Hotel stays, average (kg CO2e per room-night)'
)

# Ground transport: kg CO2e per passenger-km
GROUND_FACTORS = {
    'car':      (Decimal('0.17100'), 'DEFRA 2023: Average car (market mix, kg CO2e/km)'),
    'taxi':     (Decimal('0.21100'), 'DEFRA 2023: Taxi (kg CO2e/km)'),
    'ola':      (Decimal('0.21100'), 'DEFRA 2023: Taxi (kg CO2e/km)'),
    'uber':     (Decimal('0.21100'), 'DEFRA 2023: Taxi (kg CO2e/km)'),
    'bus':      (Decimal('0.02890'), 'DEFRA 2023: Local bus (kg CO2e/km)'),
    'rail':     (Decimal('0.03549'), 'DEFRA 2023: National rail (kg CO2e/km)'),
    'metro':    (Decimal('0.02800'), 'DEFRA 2023: Light rail/metro (kg CO2e/km)'),
    'rental':   (Decimal('0.17100'), 'DEFRA 2023: Rental car average (kg CO2e/km)'),
    'default':  (Decimal('0.17100'), 'DEFRA 2023: Average car (default, kg CO2e/km)'),
}

SHORT_HAUL_KM_THRESHOLD = 3700  # km — DEFRA boundary for short/long haul
