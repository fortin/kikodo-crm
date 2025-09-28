from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Company, Contact, Deal, Activity, Tag, 
    ContactTag, CompanyTag, DealTag, Pipeline, PipelineStage
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']
        read_only_fields = ['id']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color', 'description']


class CompanySerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    full_address = serializers.ReadOnlyField()
    
    class Meta:
        model = Company
        fields = [
            'id', 'name', 'industry', 'website', 'phone', 'email',
            'address', 'city', 'state', 'country', 'postal_code',
            'description', 'annual_revenue', 'employee_count',
            'owner', 'is_active', 'created_at', 'updated_at', 'full_address'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ContactSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    company_id = serializers.IntegerField(write_only=True, required=False)
    owner = UserSerializer(read_only=True)
    full_name = serializers.ReadOnlyField()
    full_address = serializers.ReadOnlyField()
    
    class Meta:
        model = Contact
        fields = [
            'id', 'salutation', 'first_name', 'last_name', 'email',
            'phone', 'mobile', 'job_title', 'department', 'company',
            'company_id', 'address', 'city', 'state', 'country',
            'postal_code', 'status', 'source', 'notes', 'owner',
            'is_active', 'linkedin_url', 'twitter_handle',
            'created_at', 'updated_at', 'full_name', 'full_address'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        company_id = validated_data.pop('company_id', None)
        if company_id:
            validated_data['company_id'] = company_id
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        company_id = validated_data.pop('company_id', None)
        if company_id:
            validated_data['company_id'] = company_id
        return super().update(instance, validated_data)


class DealSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    contact_id = serializers.IntegerField(write_only=True)
    company = CompanySerializer(read_only=True)
    company_id = serializers.IntegerField(write_only=True, required=False)
    owner = UserSerializer(read_only=True)
    weighted_amount = serializers.ReadOnlyField()
    days_to_close = serializers.ReadOnlyField()
    
    class Meta:
        model = Deal
        fields = [
            'id', 'name', 'description', 'amount', 'currency',
            'stage', 'probability', 'priority', 'contact', 'contact_id',
            'company', 'company_id', 'owner', 'expected_close_date',
            'actual_close_date', 'notes', 'is_active', 'weighted_amount',
            'days_to_close', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        contact_id = validated_data.pop('contact_id')
        company_id = validated_data.pop('company_id', None)
        validated_data['contact_id'] = contact_id
        if company_id:
            validated_data['company_id'] = company_id
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        contact_id = validated_data.pop('contact_id', None)
        company_id = validated_data.pop('company_id', None)
        if contact_id:
            validated_data['contact_id'] = contact_id
        if company_id:
            validated_data['company_id'] = company_id
        return super().update(instance, validated_data)


class ActivitySerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    contact_id = serializers.IntegerField(write_only=True, required=False)
    company = CompanySerializer(read_only=True)
    company_id = serializers.IntegerField(write_only=True, required=False)
    deal = DealSerializer(read_only=True)
    deal_id = serializers.IntegerField(write_only=True, required=False)
    owner = UserSerializer(read_only=True)
    
    class Meta:
        model = Activity
        fields = [
            'id', 'activity_type', 'subject', 'description', 'status',
            'contact', 'contact_id', 'company', 'company_id',
            'deal', 'deal_id', 'owner', 'due_date', 'completed_date',
            'duration_minutes', 'outcome', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_date']
    
    def create(self, validated_data):
        contact_id = validated_data.pop('contact_id', None)
        company_id = validated_data.pop('company_id', None)
        deal_id = validated_data.pop('deal_id', None)
        
        if contact_id:
            validated_data['contact_id'] = contact_id
        if company_id:
            validated_data['company_id'] = company_id
        if deal_id:
            validated_data['deal_id'] = deal_id
            
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        contact_id = validated_data.pop('contact_id', None)
        company_id = validated_data.pop('company_id', None)
        deal_id = validated_data.pop('deal_id', None)
        
        if contact_id:
            validated_data['contact_id'] = contact_id
        if company_id:
            validated_data['company_id'] = company_id
        if deal_id:
            validated_data['deal_id'] = deal_id
            
        return super().update(instance, validated_data)


class PipelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pipeline
        fields = ['id', 'name', 'description', 'is_default', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class PipelineStageSerializer(serializers.ModelSerializer):
    pipeline = PipelineSerializer(read_only=True)
    pipeline_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = PipelineStage
        fields = [
            'id', 'pipeline', 'pipeline_id', 'name', 'order',
            'probability', 'is_closed', 'is_won', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        pipeline_id = validated_data.pop('pipeline_id')
        validated_data['pipeline_id'] = pipeline_id
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        pipeline_id = validated_data.pop('pipeline_id', None)
        if pipeline_id:
            validated_data['pipeline_id'] = pipeline_id
        return super().update(instance, validated_data)


# Tag relationship serializers
class ContactTagSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    contact_id = serializers.IntegerField(write_only=True)
    tag = TagSerializer(read_only=True)
    tag_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = ContactTag
        fields = ['id', 'contact', 'contact_id', 'tag', 'tag_id']
    
    def create(self, validated_data):
        contact_id = validated_data.pop('contact_id')
        tag_id = validated_data.pop('tag_id')
        validated_data['contact_id'] = contact_id
        validated_data['tag_id'] = tag_id
        return super().create(validated_data)


class CompanyTagSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    company_id = serializers.IntegerField(write_only=True)
    tag = TagSerializer(read_only=True)
    tag_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = CompanyTag
        fields = ['id', 'company', 'company_id', 'tag', 'tag_id']
    
    def create(self, validated_data):
        company_id = validated_data.pop('company_id')
        tag_id = validated_data.pop('tag_id')
        validated_data['company_id'] = company_id
        validated_data['tag_id'] = tag_id
        return super().create(validated_data)


class DealTagSerializer(serializers.ModelSerializer):
    deal = DealSerializer(read_only=True)
    deal_id = serializers.IntegerField(write_only=True)
    tag = TagSerializer(read_only=True)
    tag_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = DealTag
        fields = ['id', 'deal', 'deal_id', 'tag', 'tag_id']
    
    def create(self, validated_data):
        deal_id = validated_data.pop('deal_id')
        tag_id = validated_data.pop('tag_id')
        validated_data['deal_id'] = deal_id
        validated_data['tag_id'] = tag_id
        return super().create(validated_data)
