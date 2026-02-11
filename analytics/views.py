from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import (
    ActivitySummary,
    Base,
    ContactEngagement,
    CustomField,
    CustomFieldValue,
    CustomMetric,
    DashboardTemplate,
    DashboardView,
    DashboardWidget,
    DealForecast,
    MetricDataPoint,
    PipelineSnapshot,
    Record,
    Report,
    SalesGoal,
    Table,
    TableField,
)
from .serializers import (
    ActivitySummarySerializer,
    BaseSerializer,
    ContactEngagementSerializer,
    CustomFieldSerializer,
    CustomFieldValueSerializer,
    CustomMetricSerializer,
    DashboardTemplateSerializer,
    DashboardViewSerializer,
    DashboardWidgetSerializer,
    DealForecastSerializer,
    MetricDataPointSerializer,
    PipelineSnapshotSerializer,
    RecordSerializer,
    ReportSerializer,
    SalesGoalSerializer,
    TableFieldSerializer,
    TableSerializer,
)
from .utils import CSVImporter


@login_required
def analytics_dashboard(request):
    """Analytics dashboard view"""
    context = {}
    return render(request, "analytics/dashboard.html", context)


@login_required
def analytics_reports(request):
    """Analytics reports view"""
    context = {}
    return render(request, "analytics/reports.html", context)


@login_required
def analytics_templates(request):
    """Dashboard templates view"""
    context = {}
    return render(request, "analytics/templates.html", context)


@login_required
def analytics_bases(request):
    """Airtable-style bases view"""
    context = {}
    return render(request, "analytics/bases.html", context)


class DashboardWidgetViewSet(viewsets.ModelViewSet):
    queryset = DashboardWidget.objects.all()
    serializer_class = DashboardWidgetSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["widget_type", "is_active", "user"]
    search_fields = ["name", "description"]
    ordering_fields = ["order", "name"]
    ordering = ["user", "order"]


class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["report_type", "is_public", "is_active", "created_by"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SalesGoalViewSet(viewsets.ModelViewSet):
    queryset = SalesGoal.objects.all()
    serializer_class = SalesGoalSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["goal_type", "period_type", "is_active", "user"]
    search_fields = ["name"]
    ordering_fields = ["start_date", "end_date", "target_value"]
    ordering = ["-start_date"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ActivitySummaryViewSet(viewsets.ModelViewSet):
    queryset = ActivitySummary.objects.all()
    serializer_class = ActivitySummarySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["date", "user"]
    ordering_fields = ["date"]
    ordering = ["-date"]


class PipelineSnapshotViewSet(viewsets.ModelViewSet):
    queryset = PipelineSnapshot.objects.all()
    serializer_class = PipelineSnapshotSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["date", "stage"]
    search_fields = ["stage"]
    ordering_fields = ["date", "stage"]
    ordering = ["-date", "stage"]


class ContactEngagementViewSet(viewsets.ModelViewSet):
    queryset = ContactEngagement.objects.all()
    serializer_class = ContactEngagementSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["date", "contact"]
    search_fields = ["contact__first_name", "contact__last_name"]
    ordering_fields = ["date"]
    ordering = ["-date"]


class DealForecastViewSet(viewsets.ModelViewSet):
    queryset = DealForecast.objects.all()
    serializer_class = DealForecastSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["forecast_date", "confidence_level"]
    search_fields = ["deal__name", "notes"]
    ordering_fields = ["forecast_date"]
    ordering = ["-forecast_date"]


class CustomFieldViewSet(viewsets.ModelViewSet):
    queryset = CustomField.objects.all()
    serializer_class = CustomFieldSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["field_type", "entity_type", "is_required", "is_active"]
    search_fields = ["name", "label"]
    ordering_fields = ["entity_type", "order", "name"]
    ordering = ["entity_type", "order"]


class CustomFieldValueViewSet(viewsets.ModelViewSet):
    queryset = CustomFieldValue.objects.all()
    serializer_class = CustomFieldValueSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["custom_field", "content_type"]
    search_fields = ["custom_field__name", "text_value"]


class DashboardTemplateViewSet(viewsets.ModelViewSet):
    queryset = DashboardTemplate.objects.all()
    serializer_class = DashboardTemplateSerializer
    permission_classes = [permissions.AllowAny]  # Temporarily allow any for testing
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["period_type", "is_active", "is_public", "created_by"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def import_csv(self, request, pk=None):
        """Import CSV data for this template"""
        template = self.get_object()

        if "csv_file" not in request.FILES:
            return Response(
                {"error": "No CSV file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        csv_file = request.FILES["csv_file"]

        try:
            importer = CSVImporter(template.id, request.user.id)
            result = importer.import_metrics(csv_file)

            if result["success"]:
                return Response(
                    {
                        "message": "CSV imported successfully",
                        "created_count": result["created_count"],
                        "updated_count": result["updated_count"],
                        "warnings": result["warnings"],
                    }
                )
            else:
                return Response(
                    {
                        "error": result["error"],
                        "errors": result["errors"],
                        "warnings": result["warnings"],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            return Response(
                {"error": f"Import failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CustomMetricViewSet(viewsets.ModelViewSet):
    queryset = CustomMetric.objects.all()
    serializer_class = CustomMetricSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["template", "metric_type", "period"]
    search_fields = ["metric_name", "description"]
    ordering_fields = ["template", "period", "metric_name"]
    ordering = ["template", "period", "metric_name"]

    @action(detail=True, methods=["get"])
    def progress_summary(self, request, pk=None):
        """Get progress summary for a metric"""
        metric = self.get_object()

        return Response(
            {
                "metric_name": metric.metric_name,
                "target_value": metric.target_value,
                "actual_value": metric.actual_value,
                "percentage_achieved": metric.percentage_achieved,
                "is_on_track": metric.is_on_track,
                "unit": metric.unit,
            }
        )


class MetricDataPointViewSet(viewsets.ModelViewSet):
    queryset = MetricDataPoint.objects.all()
    serializer_class = MetricDataPointSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["metric__template", "date_recorded"]
    search_fields = ["metric__metric_name", "notes"]
    ordering_fields = ["date_recorded"]
    ordering = ["-date_recorded"]


class DashboardViewViewSet(viewsets.ModelViewSet):
    queryset = DashboardView.objects.all()
    serializer_class = DashboardViewSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "template",
        "chart_type",
        "is_default",
        "is_public",
        "created_by",
    ]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# New Airtable-style ViewSets
class BaseViewSet(viewsets.ModelViewSet):
    queryset = Base.objects.all()
    serializer_class = BaseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "is_public", "created_by", "color"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["get"])
    def tables(self, request, pk=None):
        """Get all tables in this base"""
        base = self.get_object()
        tables = Table.objects.filter(base=base)
        serializer = TableSerializer(tables, many=True)
        return Response(serializer.data)


class TableViewSet(viewsets.ModelViewSet):
    queryset = Table.objects.all()
    serializer_class = TableSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["base", "is_active", "color", "default_view"]
    search_fields = ["name", "description", "base__name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["base", "name"]

    @action(detail=True, methods=["get"])
    def records(self, request, pk=None):
        """Get all records in this table"""
        table = self.get_object()
        records = Record.objects.filter(table=table)
        serializer = RecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def fields(self, request, pk=None):
        """Get all fields in this table"""
        table = self.get_object()
        fields = TableField.objects.filter(table=table).order_by("order", "name")
        serializer = TableFieldSerializer(fields, many=True)
        return Response(serializer.data)


class TableFieldViewSet(viewsets.ModelViewSet):
    queryset = TableField.objects.all()
    serializer_class = TableFieldSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["table", "field_type", "is_primary", "is_required"]
    search_fields = ["name", "description"]
    ordering_fields = ["order", "name"]
    ordering = ["table", "order", "name"]


class RecordViewSet(viewsets.ModelViewSet):
    queryset = Record.objects.all()
    serializer_class = RecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["table"]
    search_fields = ["data"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["patch"])
    def update_field(self, request, pk=None):
        """Update a single field in a record"""
        record = self.get_object()
        field_name = request.data.get("field_name")
        field_value = request.data.get("field_value")

        if not field_name:
            return Response(
                {"error": "field_name is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Update the field value
        record.data[field_name] = field_value
        record.save()

        serializer = self.get_serializer(record)
        return Response(serializer.data)
