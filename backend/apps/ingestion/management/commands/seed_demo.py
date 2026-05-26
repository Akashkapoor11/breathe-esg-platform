"""
python manage.py seed_demo

Creates demo org, users, and sample emission records so the
deployed app has data visible on first login.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Organization
from apps.ingestion.models import IngestionJob, EmissionRecord, AuditEvent
from datetime import date
from decimal import Decimal
import uuid

User = get_user_model()


SAP_RECORDS = [
    {
        'scope': 1, 'category': 'mobile_combustion',
        'activity_description': 'Diesel - Fleet vehicles at Delhi Plant',
        'activity_value': 5000.0, 'activity_unit': 'L',
        'activity_value_normalized': 5000.0, 'activity_unit_normalized': 'L',
        'emission_factor': 2.68737, 'emission_factor_unit': 'kg CO2e/L',
        'emission_factor_source': 'DEFRA 2023 Table 1A: Gas Oil/Diesel (kg CO2e/L)',
        'co2e_kg': 13436.85,
        'period_start': date(2024, 1, 15), 'period_end': date(2024, 1, 16),
        'source_ref': 'SAP Doc: 4500012345 | Plant: PLNT_DEL | Material: MAT-DIESEL',
        'raw_data': {
            'MANDT': '100', 'BUKRS': '1000', 'WERKS': 'PLNT_DEL',
            'BELNR': '4500012345', 'BLDAT': '20240115', 'BUDAT': '20240116',
            'MATNR': 'MAT-DIESEL', 'MAKTX': 'Diesel Kraftstoff',
            'MENGE': '5000', 'MEINS': 'L', 'NETPR': '87500', 'WAERS': 'INR',
            'KOSTL': 'COST_FLEET_001', 'BKTXT': 'Fleet fuel replenishment Jan-24'
        },
        'warnings': [],
    },
    {
        'scope': 1, 'category': 'mobile_combustion',
        'activity_description': 'Benzin (Petrol) - Fleet vehicles at Mumbai Plant',
        'activity_value': 2500.0, 'activity_unit': 'L',
        'activity_value_normalized': 2500.0, 'activity_unit_normalized': 'L',
        'emission_factor': 2.31420, 'emission_factor_unit': 'kg CO2e/L',
        'emission_factor_source': 'DEFRA 2023 Table 1A: Petrol (kg CO2e/L)',
        'co2e_kg': 5785.50,
        'period_start': date(2024, 1, 15), 'period_end': date(2024, 1, 16),
        'source_ref': 'SAP Doc: 4500012346 | Plant: PLNT_MUM | Material: MAT-PETROL',
        'raw_data': {
            'MANDT': '100', 'BUKRS': '1000', 'WERKS': 'PLNT_MUM',
            'BELNR': '4500012346', 'BLDAT': '20240115', 'BUDAT': '20240116',
            'MATNR': 'MAT-PETROL', 'MAKTX': 'Benzin',
            'MENGE': '2500', 'MEINS': 'L', 'NETPR': '43750', 'WAERS': 'INR',
            'KOSTL': 'COST_FLEET_002', 'BKTXT': 'Fleet fuel Jan-24 MUM'
        },
        'warnings': ['Material description is German ("Benzin") — mapped to petrol/gasoline'],
    },
    {
        'scope': 1, 'category': 'stationary_combustion',
        'activity_description': 'Erdgas (Natural Gas) - Boiler at Bangalore Plant',
        'activity_value': 1200.0, 'activity_unit': 'M3',
        'activity_value_normalized': 1200.0, 'activity_unit_normalized': 'm³',
        'emission_factor': 2.04300, 'emission_factor_unit': 'kg CO2e/m³',
        'emission_factor_source': 'DEFRA 2023 Table 1A: Natural Gas (kg CO2e/m³)',
        'co2e_kg': 2451.60,
        'period_start': date(2024, 1, 16), 'period_end': date(2024, 1, 17),
        'source_ref': 'SAP Doc: 4500012347 | Plant: PLNT_BNG | Material: MAT-NATGAS',
        'raw_data': {
            'MANDT': '100', 'BUKRS': '1000', 'WERKS': 'PLNT_BNG',
            'BELNR': '4500012347', 'BLDAT': '20240116', 'BUDAT': '20240117',
            'MATNR': 'MAT-NATGAS', 'MAKTX': 'Erdgas',
            'MENGE': '1200', 'MEINS': 'M3', 'NETPR': '24000', 'WAERS': 'INR',
            'KOSTL': 'COST_BOILER_001', 'BKTXT': 'Natural gas boiler BNG Jan-24'
        },
        'warnings': ['Material description is German ("Erdgas") — mapped to natural gas'],
    },
    {
        'scope': 1, 'category': 'mobile_combustion',
        'activity_description': 'HSD (High Speed Diesel) - Backup Generator at Chennai Plant',
        'activity_value': 800.0, 'activity_unit': 'KL',
        'activity_value_normalized': 800000.0, 'activity_unit_normalized': 'L',
        'emission_factor': 2.68737, 'emission_factor_unit': 'kg CO2e/L',
        'emission_factor_source': 'DEFRA 2023 Table 1A: Gas Oil/Diesel (kg CO2e/L)',
        'co2e_kg': 2149896.0,
        'period_start': date(2024, 1, 20), 'period_end': date(2024, 1, 20),
        'source_ref': 'SAP Doc: 4500012350 | Plant: PLNT_CHN | Material: MAT-HSD',
        'raw_data': {
            'MANDT': '100', 'BUKRS': '1000', 'WERKS': 'PLNT_CHN',
            'BELNR': '4500012350', 'BLDAT': '20240120', 'BUDAT': '20240120',
            'MATNR': 'MAT-HSD', 'MAKTX': 'High Speed Diesel',
            'MENGE': '800', 'MEINS': 'KL', 'NETPR': '5600000', 'WAERS': 'INR',
            'KOSTL': 'COST_GEN_001', 'BKTXT': 'DG set fuel Jan-24'
        },
        'warnings': [
            'Unit converted from KL to L (×1000)',
            'Unusually large quantity: 800000.0 L. Verify this isn\'t a sum row or data entry error.',
        ],
    },
]

UTILITY_RECORDS = [
    {
        'scope': 2, 'category': 'purchased_electricity',
        'activity_description': 'Electricity consumption at Plot 45, Industrial Area, Delhi (Commercial-HT)',
        'activity_value': 45230.0, 'activity_unit': 'kWh',
        'activity_value_normalized': 45230.0, 'activity_unit_normalized': 'kWh',
        'emission_factor': 0.716000, 'emission_factor_unit': 'kg CO2e/kWh',
        'emission_factor_source': 'CEA CO2 Baseline Database for the Indian Power Sector, Version 18.0, FY 2022-23, Grid Average (location-based)',
        'co2e_kg': 32384.68,
        'period_start': date(2024, 1, 5), 'period_end': date(2024, 2, 4),
        'source_ref': 'Meter: MTR-001A | Account: ACC-DL-001',
        'raw_data': {
            'Account_Number': 'ACC-DL-001', 'Meter_ID': 'MTR-001A',
            'Service_Address': 'Plot 45, Industrial Area, Delhi',
            'Billing_Period_Start': '2024-01-05', 'Billing_Period_End': '2024-02-04',
            'Usage_kWh': '45230', 'Peak_Demand_kW': '125.5',
            'Rate_Schedule': 'Commercial-HT', 'Total_Charges_INR': '542760',
        },
        'warnings': ['Billing period is 31 days (Jan 5 – Feb 4); does not align with calendar month'],
    },
    {
        'scope': 2, 'category': 'purchased_electricity',
        'activity_description': 'Electricity consumption at Plot 45, Industrial Area, Delhi (Warehouse) (Commercial-LT)',
        'activity_value': 8750.0, 'activity_unit': 'kWh',
        'activity_value_normalized': 8750.0, 'activity_unit_normalized': 'kWh',
        'emission_factor': 0.716000, 'emission_factor_unit': 'kg CO2e/kWh',
        'emission_factor_source': 'CEA CO2 Baseline Database for the Indian Power Sector, Version 18.0, FY 2022-23, Grid Average (location-based)',
        'co2e_kg': 6265.0,
        'period_start': date(2024, 1, 5), 'period_end': date(2024, 2, 4),
        'source_ref': 'Meter: MTR-001B | Account: ACC-DL-001',
        'raw_data': {
            'Account_Number': 'ACC-DL-001', 'Meter_ID': 'MTR-001B',
            'Service_Address': 'Plot 45, Industrial Area, Delhi (Warehouse)',
            'Billing_Period_Start': '2024-01-05', 'Billing_Period_End': '2024-02-04',
            'Usage_kWh': '8750', 'Peak_Demand_kW': '25.2',
            'Rate_Schedule': 'Commercial-LT', 'Total_Charges_INR': '105000',
        },
        'warnings': [],
    },
    {
        'scope': 2, 'category': 'purchased_electricity',
        'activity_description': 'Electricity consumption at Navi Mumbai IT Park, Block C (IT-Park-Rate)',
        'activity_value': 32100.0, 'activity_unit': 'kWh',
        'activity_value_normalized': 32100.0, 'activity_unit_normalized': 'kWh',
        'emission_factor': 0.716000, 'emission_factor_unit': 'kg CO2e/kWh',
        'emission_factor_source': 'CEA CO2 Baseline Database for the Indian Power Sector, Version 18.0, FY 2022-23, Grid Average (location-based)',
        'co2e_kg': 22983.6,
        'period_start': date(2024, 1, 1), 'period_end': date(2024, 1, 31),
        'source_ref': 'Meter: MTR-002A | Account: ACC-MH-002',
        'raw_data': {
            'Account_Number': 'ACC-MH-002', 'Meter_ID': 'MTR-002A',
            'Service_Address': 'Navi Mumbai IT Park, Block C',
            'Billing_Period_Start': '2024-01-01', 'Billing_Period_End': '2024-01-31',
            'Usage_kWh': '32100', 'Peak_Demand_kW': '89.3',
            'Rate_Schedule': 'IT-Park-Rate', 'Total_Charges_INR': '385200',
        },
        'warnings': [],
    },
]

TRAVEL_RECORDS = [
    {
        'scope': 3, 'category': 'business_travel_air',
        'activity_description': 'Flight DEL→BOM (Economy, short-haul) via IndiGo',
        'activity_value': 1388.0, 'activity_unit': 'km',
        'activity_value_normalized': 1388.0, 'activity_unit_normalized': 'km',
        'emission_factor': 0.25491, 'emission_factor_unit': 'kg CO2e/km',
        'emission_factor_source': 'DEFRA 2023: Domestic/Short-haul economy, with RF (kg CO2e/pax-km)',
        'co2e_kg': 353.81,
        'period_start': date(2024, 1, 8), 'period_end': date(2024, 1, 8),
        'source_ref': 'Trip: TRP-2024-001 | Emp: EMP-045 | DEL→BOM',
        'raw_data': {
            'Trip_ID': 'TRP-2024-001', 'Employee_ID': 'EMP-045',
            'Department': 'Engineering', 'Travel_Date': '2024-01-08',
            'Type': 'FLIGHT', 'Origin': 'DEL', 'Destination': 'BOM',
            'Class': 'ECONOMY', 'Nights': '', 'Distance_km': '',
            'Amount_INR': '', 'Vendor': 'IndiGo', 'CO2_Reported_gCO2': '',
        },
        'warnings': [
            'Distance DEL→BOM computed via haversine (1388 km). Verify against actual flight path.',
        ],
    },
    {
        'scope': 3, 'category': 'business_travel_air',
        'activity_description': 'Flight BOM→LHR (Business, long-haul) via Air India',
        'activity_value': 7192.0, 'activity_unit': 'km',
        'activity_value_normalized': 7192.0, 'activity_unit_normalized': 'km',
        'emission_factor': 0.48802, 'emission_factor_unit': 'kg CO2e/km',
        'emission_factor_source': 'DEFRA 2023: Long-haul business class, with RF (kg CO2e/pax-km)',
        'co2e_kg': 3511.89,
        'period_start': date(2024, 1, 9), 'period_end': date(2024, 1, 9),
        'source_ref': 'Trip: TRP-2024-002 | Emp: EMP-087 | BOM→LHR',
        'raw_data': {
            'Trip_ID': 'TRP-2024-002', 'Employee_ID': 'EMP-087',
            'Department': 'Sales', 'Travel_Date': '2024-01-09',
            'Type': 'FLIGHT', 'Origin': 'BOM', 'Destination': 'LHR',
            'Class': 'BUSINESS', 'Nights': '', 'Distance_km': '',
            'Amount_INR': '', 'Vendor': 'Air India', 'CO2_Reported_gCO2': '',
        },
        'warnings': [
            'Distance BOM→LHR computed via haversine (7192 km). Verify against actual flight path.',
        ],
    },
    {
        'scope': 3, 'category': 'business_travel_hotel',
        'activity_description': 'Hotel stay 2 night(s) at Marriott',
        'activity_value': 2.0, 'activity_unit': 'nights',
        'activity_value_normalized': 2.0, 'activity_unit_normalized': 'nights',
        'emission_factor': 20.8, 'emission_factor_unit': 'kg CO2e/room-night',
        'emission_factor_source': 'DEFRA 2023: Hotel stays, average (kg CO2e per room-night)',
        'co2e_kg': 41.6,
        'period_start': date(2024, 1, 10), 'period_end': date(2024, 1, 10),
        'source_ref': 'Trip: TRP-2024-003 | Emp: EMP-045',
        'raw_data': {
            'Trip_ID': 'TRP-2024-003', 'Employee_ID': 'EMP-045',
            'Department': 'Engineering', 'Travel_Date': '2024-01-10',
            'Type': 'HOTEL', 'Origin': '', 'Destination': '',
            'Class': '', 'Nights': '2', 'Distance_km': '',
            'Amount_INR': '12500', 'Vendor': 'Marriott', 'CO2_Reported_gCO2': '',
        },
        'warnings': [],
    },
    {
        'scope': 3, 'category': 'business_travel_ground',
        'activity_description': 'Ground transport via Ola (213.3 km) — estimated from fare',
        'activity_value': 213.33, 'activity_unit': 'km',
        'activity_value_normalized': 213.33, 'activity_unit_normalized': 'km',
        'emission_factor': 0.21100, 'emission_factor_unit': 'kg CO2e/km',
        'emission_factor_source': 'DEFRA 2023: Taxi (kg CO2e/km)',
        'co2e_kg': 45.01,
        'period_start': date(2024, 1, 11), 'period_end': date(2024, 1, 11),
        'source_ref': 'Trip: TRP-2024-004 | Emp: EMP-112',
        'raw_data': {
            'Trip_ID': 'TRP-2024-004', 'Employee_ID': 'EMP-112',
            'Department': 'Marketing', 'Travel_Date': '2024-01-11',
            'Type': 'CAR', 'Origin': '', 'Destination': '',
            'Class': '', 'Nights': '', 'Distance_km': '',
            'Amount_INR': '3200', 'Vendor': 'Ola', 'CO2_Reported_gCO2': '',
        },
        'warnings': [
            'Distance not given — estimated from amount ÷ ₹15/km heuristic (213.3 km). Significant uncertainty.',
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed demo organization, users, and sample emission records'

    def handle(self, *args, **options):
        # Create org
        org, _ = Organization.objects.get_or_create(
            slug='acme-corp',
            defaults={
                'name': 'Acme Manufacturing Pvt. Ltd.',
                'country': 'India',
                'reporting_year': 2024,
                'electricity_emission_factor': Decimal('0.716000'),
            }
        )
        self.stdout.write(f'Organization: {org.name}')

        # Create users
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@acme.example.com',
                'first_name': 'Admin',
                'last_name': 'User',
                'organization': org,
                'role': 'admin',
                'is_staff': True,
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()

        analyst_user, created = User.objects.get_or_create(
            username='analyst',
            defaults={
                'email': 'analyst@acme.example.com',
                'first_name': 'Priya',
                'last_name': 'Sharma',
                'organization': org,
                'role': 'analyst',
            }
        )
        if created:
            analyst_user.set_password('analyst123')
            analyst_user.save()

        self.stdout.write('Users created: admin / admin123, analyst / analyst123')

        # Skip if records already exist
        if EmissionRecord.objects.filter(org=org).exists():
            self.stdout.write('Records already exist — skipping seed')
            return

        # Create ingestion jobs
        sap_job = IngestionJob.objects.create(
            org=org, source_type='SAP',
            filename='MM_fuel_procurement_Jan2024.csv',
            uploaded_by=admin_user,
            status='COMPLETE',
            row_count=4, success_count=4, error_count=0, warning_count=2,
        )
        util_job = IngestionJob.objects.create(
            org=org, source_type='UTILITY',
            filename='electricity_Q1_2024_all_sites.csv',
            uploaded_by=admin_user,
            status='COMPLETE',
            row_count=3, success_count=3, error_count=0, warning_count=1,
        )
        travel_job = IngestionJob.objects.create(
            org=org, source_type='TRAVEL',
            filename='concur_expense_export_Jan2024.csv',
            uploaded_by=admin_user,
            status='COMPLETE',
            row_count=4, success_count=4, error_count=0, warning_count=2,
        )

        # Create records
        statuses = ['pending', 'pending', 'approved', 'flagged']
        for i, rd in enumerate(SAP_RECORDS):
            r = EmissionRecord.objects.create(
                org=org, job=sap_job,
                status=statuses[i % len(statuses)],
                reviewed_by=analyst_user if statuses[i % len(statuses)] == 'approved' else None,
                **rd
            )
            AuditEvent.objects.create(record=r, action='ingested', actor=admin_user,
                                      actor_name=admin_user.get_full_name())
            if r.status == 'approved':
                AuditEvent.objects.create(record=r, action='approved', actor=analyst_user,
                                          actor_name=analyst_user.get_full_name())

        for i, rd in enumerate(UTILITY_RECORDS):
            r = EmissionRecord.objects.create(
                org=org, job=util_job,
                status='pending' if i == 0 else 'approved',
                reviewed_by=analyst_user if i > 0 else None,
                **rd
            )
            AuditEvent.objects.create(record=r, action='ingested', actor=admin_user)

        for i, rd in enumerate(TRAVEL_RECORDS):
            r = EmissionRecord.objects.create(
                org=org, job=travel_job,
                status='pending' if i in (0, 3) else 'approved',
                reviewed_by=analyst_user if i not in (0, 3) else None,
                **rd
            )
            AuditEvent.objects.create(record=r, action='ingested', actor=admin_user)

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded {EmissionRecord.objects.filter(org=org).count()} records'
            )
        )
