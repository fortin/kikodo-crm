from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Activity,
    AuditLog,
    Company,
    CompanyTag,
    Contact,
    ContactTag,
    Deal,
    DealTag,
    NewsletterAnalytics,
    NewsletterConversion,
    NewsletterEdition,
    NewsletterPlan,
    Pipeline,
    PipelineStage,
    Signal,
    Tag,
    Team,
    UserProfile,
    Webhook,
    WelcomeAutomation,
    WelcomeEmail,
    WelcomeEnrollment,
    NewsletterTemplate,
    NewsletterTemplateSection,
    NewsletterIssue,
    NewsletterIssueSection,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "industry",
        "phone",
        "email",
        "owner",
        "is_active",
        "created_at",
    ]
    list_filter = ["industry", "is_active", "owner", "created_at"]
    search_fields = ["name", "email", "industry", "phone", "city", "state"]
    list_editable = ["is_active"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "industry", "description", "is_active")},
        ),
        ("Contact Information", {"fields": ("phone", "email", "website")}),
        ("Address", {"fields": ("address", "city", "state", "country", "postal_code")}),
        (
            "Business Information",
            {"fields": ("annual_revenue", "employee_count", "owner")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "email",
        "phone",
        "company",
        "status",
        "newsletter_subscribed",
        "owner",
        "is_active",
        "created_at",
    ]
    list_filter = ["status", "is_active", "newsletter_subscribed", "owner", "company", "created_at"]
    search_fields = ["first_name", "last_name", "email", "phone", "company__name"]
    list_editable = ["status", "is_active", "newsletter_subscribed"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "salutation",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "mobile",
                )
            },
        ),
        (
            "Professional Information",
            {"fields": ("job_title", "department", "company")},
        ),
        ("Address", {"fields": ("address", "city", "state", "country", "postal_code")}),
        (
            "CRM Information",
            {"fields": ("status", "source", "notes", "owner", "is_active", "newsletter_subscribed")},
        ),
        (
            "Social Media",
            {"fields": ("linkedin_url", "twitter_handle"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "contact",
        "company",
        "amount",
        "stage",
        "probability",
        "expected_close_date",
        "owner",
        "is_active",
    ]
    list_filter = ["stage", "priority", "is_active", "owner", "expected_close_date"]
    search_fields = [
        "name",
        "contact__first_name",
        "contact__last_name",
        "company__name",
    ]
    list_editable = ["stage", "probability", "is_active"]
    readonly_fields = ["created_at", "updated_at", "weighted_amount"]

    fieldsets = (
        (
            "Deal Information",
            {
                "fields": (
                    "name",
                    "description",
                    "amount",
                    "currency",
                    "stage",
                    "probability",
                    "priority",
                )
            },
        ),
        ("Relationships", {"fields": ("contact", "company", "owner")}),
        ("Dates", {"fields": ("expected_close_date", "actual_close_date")}),
        ("Additional Information", {"fields": ("notes", "is_active")}),
        (
            "Calculated Fields",
            {"fields": ("weighted_amount",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = [
        "subject",
        "activity_type",
        "contact",
        "company",
        "deal",
        "status",
        "due_date",
        "owner",
    ]
    list_filter = ["activity_type", "status", "owner", "due_date", "created_at"]
    search_fields = [
        "subject",
        "description",
        "contact__first_name",
        "contact__last_name",
        "company__name",
    ]
    list_editable = ["status"]
    readonly_fields = ["created_at", "updated_at", "completed_date"]

    fieldsets = (
        (
            "Activity Information",
            {"fields": ("activity_type", "subject", "description", "status")},
        ),
        ("Relationships", {"fields": ("contact", "company", "deal", "owner")}),
        ("Scheduling", {"fields": ("due_date", "completed_date", "duration_minutes")}),
        ("Outcome", {"fields": ("outcome",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "color_display", "description"]
    search_fields = ["name", "description"]

    def color_display(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px;">{}</span>',
            obj.color,
            obj.color,
        )

    color_display.short_description = "Color"


@admin.register(ContactTag)
class ContactTagAdmin(admin.ModelAdmin):
    list_display = ["contact", "tag"]
    list_filter = ["tag"]


@admin.register(CompanyTag)
class CompanyTagAdmin(admin.ModelAdmin):
    list_display = ["company", "tag"]
    list_filter = ["tag"]


@admin.register(DealTag)
class DealTagAdmin(admin.ModelAdmin):
    list_display = ["deal", "tag"]
    list_filter = ["tag"]


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ["name", "is_default", "is_active", "created_at"]
    list_filter = ["is_default", "is_active"]
    list_editable = ["is_default", "is_active"]


@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = ["name", "pipeline", "order", "probability", "is_closed", "is_won"]
    list_filter = ["pipeline", "is_closed", "is_won"]
    list_editable = ["order", "probability", "is_closed", "is_won"]
    ordering = ["pipeline", "order"]


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = [
        "headline",
        "source_url",
        "date_logged",
        "week",
        "source_type",
        "relevance",
        "status",
    ]
    list_filter = ["source_type", "relevance", "status", "date_logged"]
    search_fields = ["headline", "summary", "source_url"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "date_logged"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "timestamp",
        "user",
        "action",
        "model_name",
        "object_id",
        "object_repr",
    ]
    list_filter = ["action", "model_name"]
    search_fields = ["object_repr", "model_name"]
    readonly_fields = [
        "user",
        "action",
        "model_name",
        "object_id",
        "object_repr",
        "old_values",
        "new_values",
        "timestamp",
    ]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "description"]
    search_fields = ["name"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "team"]
    list_filter = ["team"]
    search_fields = ["user__username", "user__email"]
    fieldsets = (
        (None, {"fields": ("user", "team")}),
        (
            "Email",
            {
                "fields": ("email_signature",),
                "description": "HTML signature for outgoing emails. Falls back to EMAIL_SIGNATURE_HTML if empty.",
            },
        ),
    )


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ["name", "url", "is_active", "created_at"]
    list_filter = ["is_active"]
    list_editable = ["is_active"]
    search_fields = ["name", "url"]
    filter_horizontal = []
    readonly_fields = ["created_at", "updated_at"]


class NewsletterEditionInline(admin.TabularInline):
    model = NewsletterEdition
    extra = 0
    fields = ["quarter", "week_number", "day_of_week", "weekly_theme", "notes", "status", "url"]


@admin.register(NewsletterPlan)
class NewsletterPlanAdmin(admin.ModelAdmin):
    list_display = ["year", "name", "created_at"]
    search_fields = ["name"]
    list_editable = ["name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [NewsletterEditionInline]


class NewsletterAnalyticsInline(admin.StackedInline):
    model = NewsletterAnalytics
    extra = 0


class NewsletterConversionInline(admin.TabularInline):
    model = NewsletterConversion
    extra = 0


@admin.register(NewsletterEdition)
class NewsletterEditionAdmin(admin.ModelAdmin):
    list_display = ["plan", "quarter", "week_number", "day_of_week", "weekly_theme", "status", "sent_at", "owner"]
    list_filter = ["plan", "quarter", "status"]
    search_fields = ["weekly_theme", "subject", "notes"]
    list_editable = ["status"]
    readonly_fields = ["created_at", "updated_at", "sent_at"]
    inlines = [NewsletterAnalyticsInline, NewsletterConversionInline]


@admin.register(NewsletterAnalytics)
class NewsletterAnalyticsAdmin(admin.ModelAdmin):
    list_display = ["edition", "subscribers_count", "sent_count", "opens_count", "clicks_count", "ad_revenue"]
    list_filter = ["edition__plan"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(NewsletterConversion)
class NewsletterConversionAdmin(admin.ModelAdmin):
    list_display = ["edition", "deal", "attribution_type", "created_at"]
    list_filter = ["attribution_type", "edition__plan"]
    search_fields = ["deal__name", "notes"]
    readonly_fields = ["created_at", "updated_at"]


class WelcomeEnrollmentInline(admin.TabularInline):
    model = WelcomeEnrollment
    extra = 0
    readonly_fields = ["enrolled_at", "next_send_at"]
    show_change_link = True


class WelcomeEmailInline(admin.TabularInline):
    model = WelcomeEmail
    extra = 0
    ordering = ["order"]


@admin.register(WelcomeAutomation)
class WelcomeAutomationAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "is_active",
        "enrollment_weight",
        "updated_at",
    ]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    inlines = [WelcomeEmailInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(WelcomeEmail)
class WelcomeEmailAdmin(admin.ModelAdmin):
    list_display = ["automation", "order", "subject", "offset_hours", "updated_at"]
    list_filter = ["automation"]
    list_editable = ["subject", "offset_hours"]
    ordering = ["automation", "order"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(WelcomeEnrollment)
class WelcomeEnrollmentAdmin(admin.ModelAdmin):
    list_display = [
        "contact",
        "automation",
        "enrolled_at",
        "current_step_index",
        "next_send_at",
        "status",
    ]
    list_filter = ["status", "automation"]
    search_fields = ["contact__first_name", "contact__last_name", "contact__email"]
    readonly_fields = ["created_at", "updated_at"]


class NewsletterTemplateSectionInline(admin.TabularInline):
    model = NewsletterTemplateSection
    extra = 0
    ordering = ["order"]


@admin.register(NewsletterTemplate)
class NewsletterTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]
    inlines = [NewsletterTemplateSectionInline]
    readonly_fields = ["created_at", "updated_at"]


class NewsletterIssueSectionInline(admin.TabularInline):
    model = NewsletterIssueSection
    extra = 0
    ordering = ["order"]


@admin.register(NewsletterIssue)
class NewsletterIssueAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "status", "sent_at", "blog_published_at", "owner", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "slug"]
    inlines = [NewsletterIssueSectionInline]
    readonly_fields = ["created_at", "updated_at", "sent_at", "blog_published_at"]
