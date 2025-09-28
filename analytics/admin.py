from django.contrib import admin
from django.utils.html import format_html
from .models import (
    DashboardWidget, Report, SalesGoal, ActivitySummary, 
    PipelineSnapshot, ContactEngagement, DealForecast, 
    CustomField, CustomFieldValue
)


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'widget_type', 'user', 'order', 'is_active']
    list_filter = ['widget_type', 'is_active', 'user']
    list_editable = ['order', 'is_active']
    ordering = ['user', 'order']


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'created_by', 'is_public', 'is_active', 'created_at']
    list_filter = ['report_type', 'is_public', 'is_active', 'created_by']
    list_editable = ['is_public', 'is_active']
    search_fields = ['name', 'description']


@admin.register(SalesGoal)
class SalesGoalAdmin(admin.ModelAdmin):
    list_display = ['name', 'goal_type', 'period_type', 'target_value', 'currency', 'start_date', 'end_date', 'user', 'is_active']
    list_filter = ['goal_type', 'period_type', 'is_active', 'user']
    list_editable = ['is_active']
    search_fields = ['name']


@admin.register(ActivitySummary)
class ActivitySummaryAdmin(admin.ModelAdmin):
    list_display = ['date', 'user', 'calls_made', 'emails_sent', 'meetings_held', 'deals_closed_won', 'revenue_closed']
    list_filter = ['date', 'user']
    ordering = ['-date']


@admin.register(PipelineSnapshot)
class PipelineSnapshotAdmin(admin.ModelAdmin):
    list_display = ['date', 'stage', 'count', 'total_value', 'weighted_value']
    list_filter = ['date', 'stage']
    ordering = ['-date', 'stage']


@admin.register(ContactEngagement)
class ContactEngagementAdmin(admin.ModelAdmin):
    list_display = ['contact', 'date', 'email_opens', 'email_clicks', 'website_visits', 'activities_count']
    list_filter = ['date', 'contact']
    search_fields = ['contact__first_name', 'contact__last_name']
    ordering = ['-date']


@admin.register(DealForecast)
class DealForecastAdmin(admin.ModelAdmin):
    list_display = ['deal', 'forecast_date', 'forecasted_amount', 'probability', 'confidence_level']
    list_filter = ['forecast_date', 'confidence_level']
    search_fields = ['deal__name']
    ordering = ['-forecast_date']


@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    list_display = ['name', 'field_type', 'entity_type', 'label', 'is_required', 'is_active', 'order']
    list_filter = ['field_type', 'entity_type', 'is_required', 'is_active']
    list_editable = ['is_required', 'is_active', 'order']
    search_fields = ['name', 'label']


@admin.register(CustomFieldValue)
class CustomFieldValueAdmin(admin.ModelAdmin):
    list_display = ['custom_field', 'content_type', 'object_id', 'get_value']
    list_filter = ['custom_field', 'content_type']
    search_fields = ['custom_field__name', 'text_value']
    
    def get_value(self, obj):
        return obj.get_value()
    get_value.short_description = 'Value'