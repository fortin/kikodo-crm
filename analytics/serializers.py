from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    DashboardWidget, Report, SalesGoal, ActivitySummary, 
    PipelineSnapshot, ContactEngagement, DealForecast, 
    CustomField, CustomFieldValue
)


class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = [
            'id', 'name', 'widget_type', 'description', 'config',
            'order', 'is_active', 'user', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ReportSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = Report
        fields = [
            'id', 'name', 'description', 'report_type', 'filters',
            'columns', 'created_by', 'is_public', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SalesGoalSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = SalesGoal
        fields = [
            'id', 'name', 'goal_type', 'period_type', 'target_value',
            'currency', 'start_date', 'end_date', 'user', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ActivitySummarySerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = ActivitySummary
        fields = [
            'id', 'date', 'user', 'calls_made', 'emails_sent',
            'meetings_held', 'tasks_completed', 'notes_added',
            'deals_created', 'deals_closed_won', 'deals_closed_lost',
            'revenue_closed', 'contacts_created', 'companies_created'
        ]
        read_only_fields = ['id']


class PipelineSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineSnapshot
        fields = [
            'id', 'date', 'stage', 'count', 'total_value', 'weighted_value'
        ]
        read_only_fields = ['id']


class ContactEngagementSerializer(serializers.ModelSerializer):
    contact = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = ContactEngagement
        fields = [
            'id', 'contact', 'date', 'email_opens', 'email_clicks',
            'website_visits', 'social_interactions', 'activities_count',
            'last_activity_date'
        ]
        read_only_fields = ['id']


class DealForecastSerializer(serializers.ModelSerializer):
    deal = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = DealForecast
        fields = [
            'id', 'deal', 'forecast_date', 'forecasted_amount',
            'probability', 'confidence_level', 'notes'
        ]
        read_only_fields = ['id']


class CustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomField
        fields = [
            'id', 'name', 'field_type', 'entity_type', 'label',
            'description', 'is_required', 'is_active', 'options',
            'order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CustomFieldValueSerializer(serializers.ModelSerializer):
    custom_field = CustomFieldSerializer(read_only=True)
    custom_field_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = CustomFieldValue
        fields = [
            'id', 'custom_field', 'custom_field_id', 'content_type',
            'object_id', 'text_value', 'number_value', 'date_value',
            'boolean_value', 'json_value'
        ]
        read_only_fields = ['id']
    
    def create(self, validated_data):
        custom_field_id = validated_data.pop('custom_field_id')
        validated_data['custom_field_id'] = custom_field_id
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        custom_field_id = validated_data.pop('custom_field_id', None)
        if custom_field_id:
            validated_data['custom_field_id'] = custom_field_id
        return super().update(instance, validated_data)
