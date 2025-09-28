from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    ActivitySummary,
    ContactEngagement,
    CustomField,
    CustomFieldValue,
    DashboardWidget,
    DealForecast,
    PipelineSnapshot,
    Report,
    SalesGoal,
)
from .serializers import (
    ActivitySummarySerializer,
    ContactEngagementSerializer,
    CustomFieldSerializer,
    CustomFieldValueSerializer,
    DashboardWidgetSerializer,
    DealForecastSerializer,
    PipelineSnapshotSerializer,
    ReportSerializer,
    SalesGoalSerializer,
)


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


class DashboardWidgetViewSet(viewsets.ModelViewSet):
    queryset = DashboardWidget.objects.all()
    serializer_class = DashboardWidgetSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["widget_type", "is_active", "user"]
    ordering_fields = ["order", "name"]
    ordering = ["user", "order"]


class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["report_type", "is_public", "is_active", "created_by"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at"]


class SalesGoalViewSet(viewsets.ModelViewSet):
    queryset = SalesGoal.objects.all()
    serializer_class = SalesGoalSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["goal_type", "period_type", "is_active", "user"]
    search_fields = ["name"]
    ordering_fields = ["start_date", "end_date", "target_value"]
    ordering = ["-start_date"]


class ActivitySummaryViewSet(viewsets.ModelViewSet):
    queryset = ActivitySummary.objects.all()
    serializer_class = ActivitySummarySerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["date", "user"]
    ordering_fields = ["date"]
    ordering = ["-date"]


class PipelineSnapshotViewSet(viewsets.ModelViewSet):
    queryset = PipelineSnapshot.objects.all()
    serializer_class = PipelineSnapshotSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["date", "stage"]
    ordering_fields = ["date", "stage"]
    ordering = ["-date", "stage"]


class ContactEngagementViewSet(viewsets.ModelViewSet):
    queryset = ContactEngagement.objects.all()
    serializer_class = ContactEngagementSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["date", "contact"]
    ordering_fields = ["date"]
    ordering = ["-date"]


class DealForecastViewSet(viewsets.ModelViewSet):
    queryset = DealForecast.objects.all()
    serializer_class = DealForecastSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["forecast_date", "confidence_level"]
    ordering_fields = ["forecast_date"]
    ordering = ["-forecast_date"]


class CustomFieldViewSet(viewsets.ModelViewSet):
    queryset = CustomField.objects.all()
    serializer_class = CustomFieldSerializer
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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["custom_field", "content_type"]
    search_fields = ["custom_field__name", "text_value"]
