from django.contrib.auth.models import User
from rest_framework import serializers

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


class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = [
            "id",
            "name",
            "widget_type",
            "description",
            "config",
            "order",
            "is_active",
            "user",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ReportSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "name",
            "description",
            "report_type",
            "filters",
            "columns",
            "created_by",
            "is_public",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SalesGoalSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = SalesGoal
        fields = [
            "id",
            "name",
            "goal_type",
            "period_type",
            "target_value",
            "currency",
            "start_date",
            "end_date",
            "user",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ActivitySummarySerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ActivitySummary
        fields = [
            "id",
            "date",
            "user",
            "calls_made",
            "emails_sent",
            "meetings_held",
            "tasks_completed",
            "notes_added",
            "deals_created",
            "deals_closed_won",
            "deals_closed_lost",
            "revenue_closed",
            "contacts_created",
            "companies_created",
        ]
        read_only_fields = ["id"]


class PipelineSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineSnapshot
        fields = ["id", "date", "stage", "count", "total_value", "weighted_value"]
        read_only_fields = ["id"]


class ContactEngagementSerializer(serializers.ModelSerializer):
    contact = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ContactEngagement
        fields = [
            "id",
            "contact",
            "date",
            "email_opens",
            "email_clicks",
            "website_visits",
            "social_interactions",
            "activities_count",
            "last_activity_date",
        ]
        read_only_fields = ["id"]


class DealForecastSerializer(serializers.ModelSerializer):
    deal = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = DealForecast
        fields = [
            "id",
            "deal",
            "forecast_date",
            "forecasted_amount",
            "probability",
            "confidence_level",
            "notes",
        ]
        read_only_fields = ["id"]


class CustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomField
        fields = [
            "id",
            "name",
            "field_type",
            "entity_type",
            "label",
            "description",
            "is_required",
            "is_active",
            "options",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CustomFieldValueSerializer(serializers.ModelSerializer):
    custom_field = CustomFieldSerializer(read_only=True)
    custom_field_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = CustomFieldValue
        fields = [
            "id",
            "custom_field",
            "custom_field_id",
            "content_type",
            "object_id",
            "text_value",
            "number_value",
            "date_value",
            "boolean_value",
            "json_value",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        custom_field_id = validated_data.pop("custom_field_id")
        validated_data["custom_field_id"] = custom_field_id
        return super().create(validated_data)

    def update(self, instance, validated_data):
        custom_field_id = validated_data.pop("custom_field_id", None)
        if custom_field_id:
            validated_data["custom_field_id"] = custom_field_id
        return super().update(instance, validated_data)


class DashboardTemplateSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    metrics_count = serializers.SerializerMethodField()

    class Meta:
        model = DashboardTemplate
        fields = [
            "id",
            "name",
            "description",
            "csv_template",
            "created_by",
            "is_active",
            "is_public",
            "period_type",
            "metrics_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_metrics_count(self, obj):
        return obj.metrics.count()


class CustomMetricSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    percentage_achieved = serializers.ReadOnlyField()
    is_on_track = serializers.ReadOnlyField()

    class Meta:
        model = CustomMetric
        fields = [
            "id",
            "template",
            "template_name",
            "metric_name",
            "description",
            "target_value",
            "actual_value",
            "period",
            "period_start_date",
            "period_end_date",
            "metric_type",
            "unit",
            "percentage_achieved",
            "is_on_track",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MetricDataPointSerializer(serializers.ModelSerializer):
    metric_name = serializers.CharField(source="metric.metric_name", read_only=True)

    class Meta:
        model = MetricDataPoint
        fields = ["id", "metric", "metric_name", "value", "date_recorded", "notes"]
        read_only_fields = ["id", "date_recorded"]


class DashboardViewSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = DashboardView
        fields = [
            "id",
            "template",
            "template_name",
            "name",
            "description",
            "created_by",
            "configuration",
            "chart_type",
            "is_default",
            "is_public",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# New Airtable-style serializers
class BaseSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    tables_count = serializers.SerializerMethodField()

    class Meta:
        model = Base
        fields = [
            "id",
            "name",
            "description",
            "icon",
            "color",
            "created_by",
            "is_active",
            "is_public",
            "tables_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_tables_count(self, obj):
        return obj.tables_count


class TableSerializer(serializers.ModelSerializer):
    base_name = serializers.CharField(source="base.name", read_only=True)
    records_count = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = [
            "id",
            "base",
            "base_name",
            "name",
            "description",
            "icon",
            "color",
            "is_active",
            "default_view",
            "records_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_records_count(self, obj):
        return obj.records_count


class TableFieldSerializer(serializers.ModelSerializer):
    table_name = serializers.CharField(source="table.name", read_only=True)

    class Meta:
        model = TableField
        fields = [
            "id",
            "table",
            "table_name",
            "name",
            "field_type",
            "description",
            "is_required",
            "is_primary",
            "order",
            "options",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RecordSerializer(serializers.ModelSerializer):
    table_name = serializers.CharField(source="table.name", read_only=True)

    class Meta:
        model = Record
        fields = ["id", "table", "table_name", "data", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_data(self, value):
        """Validate that data is a dictionary"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Data must be a dictionary/JSON object")
        return value
