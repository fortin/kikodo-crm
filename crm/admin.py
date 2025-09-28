from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Company, Contact, Deal, Activity, Tag, 
    ContactTag, CompanyTag, DealTag, Pipeline, PipelineStage
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'industry', 'phone', 'email', 'owner', 'is_active', 'created_at']
    list_filter = ['industry', 'is_active', 'owner', 'created_at']
    search_fields = ['name', 'email', 'phone', 'city', 'state']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'industry', 'description', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email', 'website')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code')
        }),
        ('Business Information', {
            'fields': ('annual_revenue', 'employee_count', 'owner')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'company', 'status', 'owner', 'is_active', 'created_at']
    list_filter = ['status', 'is_active', 'owner', 'company', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'company__name']
    list_editable = ['status', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('salutation', 'first_name', 'last_name', 'email', 'phone', 'mobile')
        }),
        ('Professional Information', {
            'fields': ('job_title', 'department', 'company')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code')
        }),
        ('CRM Information', {
            'fields': ('status', 'source', 'notes', 'owner', 'is_active')
        }),
        ('Social Media', {
            'fields': ('linkedin_url', 'twitter_handle'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact', 'company', 'amount', 'stage', 'probability', 'expected_close_date', 'owner', 'is_active']
    list_filter = ['stage', 'priority', 'is_active', 'owner', 'expected_close_date']
    search_fields = ['name', 'contact__first_name', 'contact__last_name', 'company__name']
    list_editable = ['stage', 'probability', 'is_active']
    readonly_fields = ['created_at', 'updated_at', 'weighted_amount']
    
    fieldsets = (
        ('Deal Information', {
            'fields': ('name', 'description', 'amount', 'currency', 'stage', 'probability', 'priority')
        }),
        ('Relationships', {
            'fields': ('contact', 'company', 'owner')
        }),
        ('Dates', {
            'fields': ('expected_close_date', 'actual_close_date')
        }),
        ('Additional Information', {
            'fields': ('notes', 'is_active')
        }),
        ('Calculated Fields', {
            'fields': ('weighted_amount',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['subject', 'activity_type', 'contact', 'company', 'deal', 'status', 'due_date', 'owner']
    list_filter = ['activity_type', 'status', 'owner', 'due_date', 'created_at']
    search_fields = ['subject', 'description', 'contact__first_name', 'contact__last_name', 'company__name']
    list_editable = ['status']
    readonly_fields = ['created_at', 'updated_at', 'completed_date']
    
    fieldsets = (
        ('Activity Information', {
            'fields': ('activity_type', 'subject', 'description', 'status')
        }),
        ('Relationships', {
            'fields': ('contact', 'company', 'deal', 'owner')
        }),
        ('Scheduling', {
            'fields': ('due_date', 'completed_date', 'duration_minutes')
        }),
        ('Outcome', {
            'fields': ('outcome',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color_display', 'description']
    search_fields = ['name', 'description']
    
    def color_display(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px;">{}</span>',
            obj.color,
            obj.color
        )
    color_display.short_description = 'Color'


@admin.register(ContactTag)
class ContactTagAdmin(admin.ModelAdmin):
    list_display = ['contact', 'tag']
    list_filter = ['tag']


@admin.register(CompanyTag)
class CompanyTagAdmin(admin.ModelAdmin):
    list_display = ['company', 'tag']
    list_filter = ['tag']


@admin.register(DealTag)
class DealTagAdmin(admin.ModelAdmin):
    list_display = ['deal', 'tag']
    list_filter = ['tag']


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_default', 'is_active', 'created_at']
    list_filter = ['is_default', 'is_active']
    list_editable = ['is_default', 'is_active']


@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = ['name', 'pipeline', 'order', 'probability', 'is_closed', 'is_won']
    list_filter = ['pipeline', 'is_closed', 'is_won']
    list_editable = ['order', 'probability', 'is_closed', 'is_won']
    ordering = ['pipeline', 'order']