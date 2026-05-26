from django.contrib import admin
from .models import IngestionJob, EmissionRecord, AuditEvent


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = ['filename', 'org', 'source_type', 'status',
                    'row_count', 'success_count', 'error_count', 'uploaded_at']
    list_filter = ['source_type', 'status', 'org']
    readonly_fields = ['processing_log']


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['activity_description', 'scope', 'category', 'co2e_kg',
                    'status', 'period_start', 'is_locked']
    list_filter = ['scope', 'status', 'category', 'org', 'is_locked']
    readonly_fields = ['raw_data', 'edit_history']
    search_fields = ['activity_description', 'source_ref']


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ['record', 'action', 'actor_name', 'timestamp']
    list_filter = ['action']
    readonly_fields = ['record', 'action', 'actor', 'actor_name',
                       'timestamp', 'note', 'data_before', 'data_after']
