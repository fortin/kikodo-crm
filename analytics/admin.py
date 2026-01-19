from django.contrib import admin
from django.utils.html import format_html

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


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ["name", "widget_type", "user", "order", "is_active"]
    list_filter = ["widget_type", "is_active", "user"]
    list_editable = ["order", "is_active"]
    ordering = ["user", "order"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "report_type",
        "created_by",
        "is_public",
        "is_active",
        "created_at",
    ]
    list_filter = ["report_type", "is_public", "is_active", "created_by"]
    list_editable = ["is_public", "is_active"]
    search_fields = ["name", "description"]


@admin.register(SalesGoal)
class SalesGoalAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "goal_type",
        "period_type",
        "target_value",
        "currency",
        "start_date",
        "end_date",
        "user",
        "is_active",
    ]
    list_filter = ["goal_type", "period_type", "is_active", "user"]
    list_editable = ["is_active"]
    search_fields = ["name"]


@admin.register(ActivitySummary)
class ActivitySummaryAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "user",
        "calls_made",
        "emails_sent",
        "meetings_held",
        "deals_closed_won",
        "revenue_closed",
    ]
    list_filter = ["date", "user"]
    ordering = ["-date"]


@admin.register(PipelineSnapshot)
class PipelineSnapshotAdmin(admin.ModelAdmin):
    list_display = ["date", "stage", "count", "total_value", "weighted_value"]
    list_filter = ["date", "stage"]
    ordering = ["-date", "stage"]


@admin.register(ContactEngagement)
class ContactEngagementAdmin(admin.ModelAdmin):
    list_display = [
        "contact",
        "date",
        "email_opens",
        "email_clicks",
        "website_visits",
        "activities_count",
    ]
    list_filter = ["date", "contact"]
    search_fields = ["contact__first_name", "contact__last_name"]
    ordering = ["-date"]


@admin.register(DealForecast)
class DealForecastAdmin(admin.ModelAdmin):
    list_display = [
        "deal",
        "forecast_date",
        "forecasted_amount",
        "probability",
        "confidence_level",
    ]
    list_filter = ["forecast_date", "confidence_level"]
    search_fields = ["deal__name"]
    ordering = ["-forecast_date"]


@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "field_type",
        "entity_type",
        "label",
        "is_required",
        "is_active",
        "order",
    ]
    list_filter = ["field_type", "entity_type", "is_required", "is_active"]
    list_editable = ["is_required", "is_active", "order"]
    search_fields = ["name", "label"]


@admin.register(CustomFieldValue)
class CustomFieldValueAdmin(admin.ModelAdmin):
    list_display = ["custom_field", "content_type", "object_id", "get_value"]
    list_filter = ["custom_field", "content_type"]
    search_fields = ["custom_field__name", "text_value"]

    def get_value(self, obj):
        return obj.get_value()

    get_value.short_description = "Value"


@admin.register(DashboardTemplate)
class DashboardTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "period_type",
        "created_by",
        "is_active",
        "is_public",
        "created_at",
    ]
    list_filter = ["period_type", "is_active", "is_public", "created_by"]
    list_editable = ["is_active", "is_public"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CustomMetric)
class CustomMetricAdmin(admin.ModelAdmin):
    list_display = [
        "metric_name",
        "template",
        "period",
        "target_value",
        "actual_value",
        "percentage_achieved",
        "is_on_track",
    ]
    list_filter = ["template", "metric_type", "period"]
    list_editable = ["target_value", "actual_value"]
    search_fields = ["metric_name", "description"]
    readonly_fields = ["percentage_achieved", "is_on_track", "created_at", "updated_at"]

    def percentage_achieved(self, obj):
        return f"{obj.percentage_achieved}%"

    percentage_achieved.short_description = "% Achieved"

    def is_on_track(self, obj):
        if obj.is_on_track:
            return format_html('<span style="color: green;">✓ On Track</span>')
        else:
            return format_html('<span style="color: red;">⚠ Behind</span>')

    is_on_track.short_description = "Status"


@admin.register(MetricDataPoint)
class MetricDataPointAdmin(admin.ModelAdmin):
    list_display = ["metric", "value", "date_recorded"]
    list_filter = ["metric__template", "date_recorded"]
    search_fields = ["metric__metric_name", "notes"]
    ordering = ["-date_recorded"]


@admin.register(DashboardView)
class DashboardViewAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "template",
        "chart_type",
        "created_by",
        "is_default",
        "is_public",
    ]
    list_filter = ["chart_type", "is_default", "is_public", "created_by"]
    list_editable = ["is_default", "is_public"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]


# New Airtable-style models admin
@admin.register(Base)
class BaseAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "icon",
        "color",
        "created_by",
        "tables_count",
        "is_active",
        "is_public",
        "created_at",
    ]
    list_filter = ["is_active", "is_public", "created_by", "color"]
    list_editable = ["is_active", "is_public"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at", "tables_count"]


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "base",
        "icon",
        "color",
        "records_count",
        "default_view",
        "is_active",
    ]
    list_filter = ["base", "is_active", "color", "default_view"]
    list_editable = ["is_active", "default_view"]
    search_fields = ["name", "description", "base__name"]
    readonly_fields = ["created_at", "updated_at", "records_count"]


@admin.register(TableField)
class TableFieldAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "table",
        "field_type",
        "is_primary",
        "is_required",
        "order",
    ]
    list_filter = ["table", "field_type", "is_primary", "is_required"]
    list_editable = ["is_primary", "is_required", "order"]
    search_fields = ["name", "description", "table__name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "table",
        "__str__",
        "created_at",
    ]
    list_filter = ["table", "created_at"]
    search_fields = ["table__name", "data"]
    readonly_fields = ["created_at", "updated_at"]

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:  # editing existing record
            readonly.append("data")
        return readonly
