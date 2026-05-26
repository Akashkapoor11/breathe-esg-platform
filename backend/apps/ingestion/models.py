"""
Ingestion models for Breathe ESG.

Design notes:
  - IngestionJob: one row per file upload. Immutable once created.
  - EmissionRecord: the canonical normalized emission event.
      raw_data stores the original ingested row verbatim — this is the
      source-of-truth anchor. Parsers populate the normalized fields.
  - AuditEvent: append-only log of every state change to a record.
      Never deleted, never edited.

Multi-tenancy: every model foreign-keys to Organization.
All queries in views filter by request.user.organization.
"""

import uuid
from django.db import models
from django.utils import timezone
from apps.accounts.models import CustomUser, Organization


class IngestionJob(models.Model):
    SOURCE_SAP = 'SAP'
    SOURCE_UTILITY = 'UTILITY'
    SOURCE_TRAVEL = 'TRAVEL'
    SOURCE_TYPES = [
        (SOURCE_SAP, 'SAP Fuel & Procurement (ALV CSV)'),
        (SOURCE_UTILITY, 'Utility Electricity (Portal CSV)'),
        (SOURCE_TRAVEL, 'Corporate Travel (Concur/Navan CSV)'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_COMPLETE = 'COMPLETE'
    STATUS_FAILED = 'FAILED'
    STATUS_PARTIAL = 'PARTIAL'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_PARTIAL, 'Partial (some rows failed)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='jobs')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    filename = models.CharField(max_length=500)
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    uploaded_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name='uploaded_jobs'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # Counters set after processing
    row_count = models.IntegerField(default=0, help_text="Total rows in file (excl. header)")
    success_count = models.IntegerField(default=0, help_text="Rows that produced a record")
    error_count = models.IntegerField(default=0, help_text="Rows that failed to parse")
    warning_count = models.IntegerField(default=0, help_text="Records with quality flags")

    # Structured log: list of {level, row, message}
    processing_log = models.JSONField(default=list)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"[{self.source_type}] {self.filename} — {self.uploaded_at.date()}"


# ── Controlled vocabularies ───────────────────────────────────────────────────

SCOPE_CHOICES = [
    (1, 'Scope 1 — Direct emissions'),
    (2, 'Scope 2 — Purchased energy'),
    (3, 'Scope 3 — Value chain'),
]

CATEGORY_CHOICES = [
    # Scope 1 (GHG Protocol Corporate Standard, Ch. 4)
    ('stationary_combustion', 'Stationary Combustion (Boilers, generators)'),
    ('mobile_combustion', 'Mobile Combustion (Fleet vehicles)'),
    # Scope 2
    ('purchased_electricity', 'Purchased Electricity'),
    # Scope 3, Category 6
    ('business_travel_air', 'Business Travel — Air'),
    ('business_travel_hotel', 'Business Travel — Hotel/Accommodation'),
    ('business_travel_ground', 'Business Travel — Ground (Car/Taxi)'),
    ('business_travel_rail', 'Business Travel — Rail'),
]

# Standard unit per category after normalization
NORMALIZED_UNIT_MAP = {
    'stationary_combustion': 'L',        # liters of fuel
    'mobile_combustion': 'L',            # liters of fuel
    'purchased_electricity': 'kWh',
    'business_travel_air': 'km',         # passenger-km
    'business_travel_hotel': 'nights',
    'business_travel_ground': 'km',
    'business_travel_rail': 'km',
}

RECORD_STATUS_CHOICES = [
    ('pending', 'Pending Review'),
    ('flagged', 'Flagged'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class EmissionRecord(models.Model):
    """
    One canonical emission event. Maps to a single source row.

    Source-of-truth fields:
      raw_data      — verbatim copy of the ingested CSV row (never mutated)
      source_ref    — human-readable identifier from the source system
                      (SAP document no, meter ID, trip ID)
      job           — FK back to the IngestionJob that produced this record

    Normalization chain:
      activity_value / activity_unit    — original values as-ingested
      activity_value_normalized / ...   — converted to standard unit
      emission_factor                   — kg CO2e per normalized unit
      co2e_kg                           — derived: normalized_value × factor

    Review workflow:
      pending → (analyst action) → approved | rejected | flagged
      approved + is_locked = True → cannot be changed (sent to audit)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='records')
    job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='records')

    # ── GHG Protocol classification ──────────────────────────────────────────
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=60, choices=CATEGORY_CHOICES)

    # ── Activity description ─────────────────────────────────────────────────
    # Human-readable label shown in the review dashboard
    activity_description = models.CharField(max_length=500)

    # ── Raw activity data (as-ingested, for traceability) ────────────────────
    activity_value = models.DecimalField(max_digits=18, decimal_places=4)
    activity_unit = models.CharField(max_length=50)

    # ── Normalized activity data (in standard unit for this category) ────────
    activity_value_normalized = models.DecimalField(max_digits=18, decimal_places=4)
    activity_unit_normalized = models.CharField(max_length=50)

    # ── Emission factor (kg CO2e per normalized unit) ────────────────────────
    # We store factor + source so an auditor can trace every number.
    emission_factor = models.DecimalField(max_digits=15, decimal_places=6)
    emission_factor_unit = models.CharField(max_length=100)   # e.g. "kg CO2e/L"
    emission_factor_source = models.CharField(max_length=400) # e.g. "DEFRA 2023 Table 1A Row 12"
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=4)

    # ── Time period ──────────────────────────────────────────────────────────
    # Utility bills often have billing periods that cross calendar months.
    # We store the actual period, not a coerced month.
    period_start = models.DateField()
    period_end = models.DateField()

    # ── Source tracking ──────────────────────────────────────────────────────
    source_ref = models.CharField(
        max_length=400,
        help_text="Primary key in the source system: SAP doc no, meter ID, Concur trip ID"
    )
    raw_data = models.JSONField(
        help_text="Verbatim CSV row dict as ingested. Immutable — never written after creation."
    )

    # ── Data quality flags ───────────────────────────────────────────────────
    # List of strings like "Unit assumed L (original: 'Ltr')" or
    # "Distance computed from airport codes DEL→BOM, verify haversine"
    warnings = models.JSONField(default=list)

    # ── Review workflow ──────────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=RECORD_STATUS_CHOICES, default='pending')
    review_note = models.TextField(blank=True, default='')
    reviewed_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Once locked, no further edits. Set when org exports to audit.
    is_locked = models.BooleanField(default=False)

    # ── Audit trail ──────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # List of {timestamp, actor_id, actor_name, field, old_value, new_value}
    edit_history = models.JSONField(default=list)

    class Meta:
        ordering = ['-period_start', 'scope', 'category']
        indexes = [
            models.Index(fields=['org', 'status']),
            models.Index(fields=['org', 'scope']),
            models.Index(fields=['org', 'period_start', 'period_end']),
            models.Index(fields=['job']),
            models.Index(fields=['is_locked']),
        ]

    def __str__(self):
        return (
            f"Scope {self.scope} | {self.category} | "
            f"{self.co2e_kg} kg CO2e | {self.period_start}"
        )

    def do_review(self, action, reviewer, note=''):
        """
        Transition the record's status. Raises if locked.
        Creates an AuditEvent.
        """
        if self.is_locked:
            raise ValueError("Record is locked for audit and cannot be changed.")
        if action not in ('approved', 'rejected', 'flagged', 'pending'):
            raise ValueError(f"Invalid review action: {action}")

        old_status = self.status
        self.status = action
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = note
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'])

        AuditEvent.objects.create(
            record=self,
            action=action,
            actor=reviewer,
            note=note,
            data_before={'status': old_status},
            data_after={'status': action},
        )

    def lock_for_audit(self, actor):
        if self.status != 'approved':
            raise ValueError("Only approved records can be locked for audit.")
        self.is_locked = True
        self.save(update_fields=['is_locked', 'updated_at'])
        AuditEvent.objects.create(record=self, action='locked', actor=actor)


class AuditEvent(models.Model):
    """
    Append-only log. Never updated or deleted.
    Every status change, edit, or lock creates a row here.
    """
    ACTION_CHOICES = [
        ('ingested', 'Ingested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('flagged', 'Flagged'),
        ('pending', 'Reset to Pending'),
        ('edited', 'Edited'),
        ('locked', 'Locked for Audit'),
        ('note_added', 'Note Added'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_events')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    actor = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    # Denormalized so the trail remains readable even if the user is deleted
    actor_name = models.CharField(max_length=200, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    data_before = models.JSONField(null=True, blank=True)
    data_after = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def save(self, *args, **kwargs):
        if self.actor and not self.actor_name:
            self.actor_name = self.actor.get_full_name() or self.actor.username
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.action} on {self.record_id} by {self.actor_name} at {self.timestamp}"
