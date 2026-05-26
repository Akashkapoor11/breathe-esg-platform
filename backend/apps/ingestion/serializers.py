from rest_framework import serializers
from .models import IngestionJob, EmissionRecord, AuditEvent
from apps.accounts.models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'country', 'reporting_year',
                  'electricity_emission_factor', 'electricity_factor_source']


class IngestionJobSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    source_type_label = serializers.CharField(source='get_source_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            'id', 'source_type', 'source_type_label',
            'filename', 'uploaded_by_name', 'uploaded_at',
            'status', 'status_label',
            'row_count', 'success_count', 'error_count', 'warning_count',
            'processing_log',
        ]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return None


class EmissionRecordListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for table views."""
    scope_label = serializers.CharField(source='get_scope_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    source_type = serializers.CharField(source='job.source_type', read_only=True)
    has_warnings = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'scope', 'scope_label', 'category',
            'activity_description',
            'activity_value', 'activity_unit',
            'activity_value_normalized', 'activity_unit_normalized',
            'co2e_kg',
            'period_start', 'period_end',
            'source_ref', 'source_type',
            'status', 'status_label', 'is_locked',
            'has_warnings', 'warnings',
            'reviewed_by_name', 'reviewed_at',
            'created_at',
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None

    def get_has_warnings(self, obj):
        return bool(obj.warnings)


class EmissionRecordDetailSerializer(EmissionRecordListSerializer):
    """Full serializer including raw_data and audit events."""
    audit_events = serializers.SerializerMethodField()
    job = IngestionJobSerializer(read_only=True)
    emission_factor_info = serializers.SerializerMethodField()

    class Meta(EmissionRecordListSerializer.Meta):
        fields = EmissionRecordListSerializer.Meta.fields + [
            'job', 'raw_data', 'edit_history',
            'emission_factor', 'emission_factor_unit', 'emission_factor_source',
            'emission_factor_info',
            'review_note', 'audit_events',
        ]

    def get_audit_events(self, obj):
        events = obj.audit_events.all()[:20]
        return [
            {
                'action': e.action,
                'actor_name': e.actor_name,
                'timestamp': e.timestamp,
                'note': e.note,
                'data_before': e.data_before,
                'data_after': e.data_after,
            }
            for e in events
        ]

    def get_emission_factor_info(self, obj):
        return {
            'value': str(obj.emission_factor),
            'unit': obj.emission_factor_unit,
            'source': obj.emission_factor_source,
        }


class ReviewActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approved', 'rejected', 'flagged', 'pending'])
    note = serializers.CharField(required=False, allow_blank=True, default='')


class BulkReviewSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=500,
    )
    action = serializers.ChoiceField(choices=['approved', 'rejected', 'flagged'])
    note = serializers.CharField(required=False, allow_blank=True, default='')


class DashboardStatsSerializer(serializers.Serializer):
    total_co2e_kg = serializers.DecimalField(max_digits=18, decimal_places=2)
    scope_breakdown = serializers.DictField()
    category_breakdown = serializers.DictField()
    status_counts = serializers.DictField()
    source_counts = serializers.DictField()
    recent_jobs = IngestionJobSerializer(many=True)
    records_with_warnings = serializers.IntegerField()
    pending_review = serializers.IntegerField()
