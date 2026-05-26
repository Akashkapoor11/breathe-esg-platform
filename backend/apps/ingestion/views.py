import csv
import io
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import IngestionJob, EmissionRecord, AuditEvent
from .serializers import (
    IngestionJobSerializer,
    EmissionRecordListSerializer,
    EmissionRecordDetailSerializer,
    ReviewActionSerializer,
    BulkReviewSerializer,
)
from .parsers.sap import parse_sap_csv
from .parsers.utility import parse_utility_csv
from .parsers.travel import parse_travel_csv


PARSERS = {
    IngestionJob.SOURCE_SAP: parse_sap_csv,
    IngestionJob.SOURCE_UTILITY: parse_utility_csv,
    IngestionJob.SOURCE_TRAVEL: parse_travel_csv,
}


class IngestionJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngestionJobSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return IngestionJob.objects.filter(
            org=self.request.user.organization
        ).prefetch_related('records')

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        """
        POST /api/jobs/upload/
        Accepts: multipart/form-data with fields:
          - file: the CSV file
          - source_type: SAP | UTILITY | TRAVEL
        """
        file_obj = request.FILES.get('file')
        source_type = request.data.get('source_type', '').upper()

        if not file_obj:
            return Response({'error': 'No file provided.'}, status=400)
        if source_type not in PARSERS:
            return Response(
                {'error': f"source_type must be one of: {', '.join(PARSERS.keys())}"},
                status=400
            )

        org = request.user.organization
        if not org:
            return Response({'error': 'User has no organization assigned.'}, status=403)

        # Create job record
        job = IngestionJob.objects.create(
            org=org,
            source_type=source_type,
            filename=file_obj.name,
            file=file_obj,
            uploaded_by=request.user,
            status=IngestionJob.STATUS_PROCESSING,
        )

        # Parse the file
        try:
            file_bytes = job.file.read()
            parse_fn = PARSERS[source_type]
            record_dicts, log_entries = parse_fn(file_bytes, org)
        except Exception as exc:
            job.status = IngestionJob.STATUS_FAILED
            job.processing_log = [{'level': 'error', 'row': 0,
                                    'message': f"Parser crashed: {str(exc)}"}]
            job.save(update_fields=['status', 'processing_log'])
            return Response(
                {'error': f'Parser error: {str(exc)}', 'job_id': str(job.id)},
                status=500
            )

        # Bulk-create EmissionRecord objects
        created = 0
        errors = 0
        warnings = 0
        error_log = []

        records_to_create = []
        for rd in record_dicts:
            try:
                rec = EmissionRecord(
                    org=org,
                    job=job,
                    scope=rd['scope'],
                    category=rd['category'],
                    activity_description=rd['activity_description'],
                    activity_value=rd['activity_value'],
                    activity_unit=rd['activity_unit'],
                    activity_value_normalized=rd['activity_value_normalized'],
                    activity_unit_normalized=rd['activity_unit_normalized'],
                    emission_factor=rd['emission_factor'],
                    emission_factor_unit=rd['emission_factor_unit'],
                    emission_factor_source=rd['emission_factor_source'],
                    co2e_kg=rd['co2e_kg'],
                    period_start=rd['period_start'],
                    period_end=rd['period_end'],
                    source_ref=rd['source_ref'],
                    raw_data=rd['raw_data'],
                    warnings=rd.get('warnings', []),
                    status='pending',
                )
                records_to_create.append(rec)
                if rd.get('warnings'):
                    warnings += 1
            except Exception as exc:
                errors += 1
                error_log.append({'level': 'error', 'row': 0,
                                   'message': f"Record build error: {str(exc)}"})

        EmissionRecord.objects.bulk_create(records_to_create)
        created = len(records_to_create)

        # Create AuditEvents for ingested records
        audit_events = [
            AuditEvent(record=r, action='ingested', actor=request.user,
                       actor_name=request.user.get_full_name() or request.user.username)
            for r in records_to_create
        ]
        AuditEvent.objects.bulk_create(audit_events)

        # Error rows from parser log
        parser_errors = sum(1 for e in log_entries if e.get('level') == 'error')
        errors += parser_errors

        # Determine final status
        if created == 0 and errors > 0:
            final_status = IngestionJob.STATUS_FAILED
        elif errors > 0:
            final_status = IngestionJob.STATUS_PARTIAL
        else:
            final_status = IngestionJob.STATUS_COMPLETE

        job.status = final_status
        job.row_count = created + errors
        job.success_count = created
        job.error_count = errors
        job.warning_count = warnings
        job.processing_log = log_entries + error_log
        job.save(update_fields=[
            'status', 'row_count', 'success_count', 'error_count',
            'warning_count', 'processing_log'
        ])

        return Response(
            IngestionJobSerializer(job, context={'request': request}).data,
            status=201
        )


class EmissionRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/records/          — list with filters
    GET  /api/records/{id}/     — detail
    POST /api/records/{id}/review/   — review action
    POST /api/records/bulk-review/   — bulk review
    """

    def get_queryset(self):
        org = self.request.user.organization
        qs = EmissionRecord.objects.filter(org=org).select_related(
            'job', 'reviewed_by'
        )

        # Filters
        params = self.request.query_params
        scope = params.get('scope')
        if scope:
            qs = qs.filter(scope=scope)

        src = params.get('source')
        if src:
            qs = qs.filter(job__source_type=src.upper())

        st = params.get('status')
        if st:
            qs = qs.filter(status=st)

        job_id = params.get('job_id')
        if job_id:
            qs = qs.filter(job_id=job_id)

        has_warnings = params.get('has_warnings')
        if has_warnings == 'true':
            qs = qs.exclude(warnings=[])
        elif has_warnings == 'false':
            qs = qs.filter(warnings=[])

        date_start = params.get('date_start')
        if date_start:
            qs = qs.filter(period_start__gte=date_start)

        date_end = params.get('date_end')
        if date_end:
            qs = qs.filter(period_end__lte=date_end)

        search = params.get('search')
        if search:
            qs = qs.filter(
                Q(activity_description__icontains=search) |
                Q(source_ref__icontains=search) |
                Q(category__icontains=search)
            )

        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EmissionRecordDetailSerializer
        return EmissionRecordListSerializer

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        record = self.get_object()
        ser = ReviewActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        if record.is_locked:
            return Response(
                {'error': 'Record is locked for audit and cannot be changed.'},
                status=400
            )

        record.do_review(
            action=ser.validated_data['action'],
            reviewer=request.user,
            note=ser.validated_data.get('note', ''),
        )

        return Response(EmissionRecordDetailSerializer(record, context={'request': request}).data)

    @action(detail=False, methods=['post'])
    def bulk_review(self, request):
        ser = BulkReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        org = request.user.organization
        ids = ser.validated_data['ids']
        action_val = ser.validated_data['action']
        note = ser.validated_data.get('note', '')

        records = EmissionRecord.objects.filter(
            org=org, id__in=ids, is_locked=False
        )

        updated = 0
        now = timezone.now()
        audit_events = []

        for rec in records:
            old_status = rec.status
            rec.status = action_val
            rec.reviewed_by = request.user
            rec.reviewed_at = now
            rec.review_note = note
            updated += 1

            audit_events.append(AuditEvent(
                record=rec,
                action=action_val,
                actor=request.user,
                actor_name=request.user.get_full_name() or request.user.username,
                note=note,
                data_before={'status': old_status},
                data_after={'status': action_val},
            ))

        EmissionRecord.objects.bulk_update(
            records,
            ['status', 'reviewed_by', 'reviewed_at', 'review_note']
        )
        AuditEvent.objects.bulk_create(audit_events)

        return Response({'updated': updated})

    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        GET /api/records/export/?status=approved
        Returns CSV of approved records for audit submission.
        """
        org = request.user.organization
        records = EmissionRecord.objects.filter(org=org, status='approved')

        response_data = []
        for r in records:
            response_data.append({
                'id': str(r.id),
                'scope': r.scope,
                'category': r.category,
                'activity_description': r.activity_description,
                'activity_value': r.activity_value,
                'activity_unit': r.activity_unit,
                'activity_value_normalized': r.activity_value_normalized,
                'activity_unit_normalized': r.activity_unit_normalized,
                'emission_factor': r.emission_factor,
                'emission_factor_unit': r.emission_factor_unit,
                'emission_factor_source': r.emission_factor_source,
                'co2e_kg': r.co2e_kg,
                'period_start': r.period_start,
                'period_end': r.period_end,
                'source_ref': r.source_ref,
                'source_type': r.job.source_type,
                'reviewed_by': r.reviewed_by.username if r.reviewed_by else '',
                'reviewed_at': r.reviewed_at,
            })

        from django.http import HttpResponse
        output = io.StringIO()
        if response_data:
            writer = csv.DictWriter(output, fieldnames=response_data[0].keys())
            writer.writeheader()
            writer.writerows(response_data)

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="approved_emissions.csv"'
        return response


class DashboardStatsView(APIView):
    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({'error': 'No organization'}, status=400)

        records = EmissionRecord.objects.filter(org=org)

        total_co2e = records.aggregate(t=Sum('co2e_kg'))['t'] or 0

        scope_breakdown = {}
        for scope in [1, 2, 3]:
            val = records.filter(scope=scope).aggregate(t=Sum('co2e_kg'))['t'] or 0
            scope_breakdown[f'scope_{scope}'] = float(val)

        category_breakdown = {}
        for cat_code, cat_label in EmissionRecord._meta.get_field('category').choices:
            val = records.filter(category=cat_code).aggregate(t=Sum('co2e_kg'))['t'] or 0
            if val > 0:
                category_breakdown[cat_code] = float(val)

        status_counts = {}
        for st_code, _ in EmissionRecord._meta.get_field('status').choices:
            status_counts[st_code] = records.filter(status=st_code).count()

        source_counts = {}
        for src_code, _ in IngestionJob.SOURCE_TYPES:
            cnt = records.filter(job__source_type=src_code).count()
            source_counts[src_code] = cnt

        recent_jobs = IngestionJob.objects.filter(org=org)[:5]

        return Response({
            'total_co2e_kg': float(total_co2e),
            'scope_breakdown': scope_breakdown,
            'category_breakdown': category_breakdown,
            'status_counts': status_counts,
            'source_counts': source_counts,
            'records_with_warnings': records.exclude(warnings=[]).count(),
            'pending_review': records.filter(status='pending').count(),
            'recent_jobs': IngestionJobSerializer(recent_jobs, many=True).data,
        })
