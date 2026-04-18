from django import forms
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet

from .models import (
    Activity,
    ActivityThread,
    Company,
    Contact,
    Deal,
    NewsletterAnalytics,
    NewsletterEdition,
    NewsletterIssue,
    NewsletterIssueSection,
    NewsletterPlan,
    NewsletterTemplate,
    NewsletterTemplateSection,
    OperatingArea,
    PainSignal,
    PainType,
    Pipeline,
    PipelineStage,
    Sequence,
    SequenceStep,
    Signal,
    WelcomeAutomation,
    WelcomeEmail,
)


class ContactForm(forms.ModelForm):
    """Form for creating and editing contacts."""

    class Meta:
        model = Contact
        fields = [
            "salutation",
            "first_name",
            "last_name",
            "email",
            "phone",
            "mobile",
            "job_title",
            "department",
            "company",
            "status",
            "outreach_status",
            "source",
            "notes",
            "verified",
            "linkedin",
            "twitter_handle",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }


class CompanyForm(forms.ModelForm):
    """Form for creating and editing companies."""

    class Meta:
        model = Company
        fields = [
            "name",
            "industry",
            "website",
            "linkedin_url",
            "phone",
            "email",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "description",
            "annual_revenue",
            "employee_count",
            "facility_count",
            "priority_tier",
            "competitor",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }


class DealForm(forms.ModelForm):
    """Form for creating and editing deals."""

    class Meta:
        model = Deal
        fields = [
            "name",
            "description",
            "amount",
            "currency",
            "pipeline",
            "pipeline_stage",
            "probability",
            "priority",
            "contact",
            "company",
            "owner",
            "expected_close_date",
            "actual_close_date",
            "notes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "expected_close_date": forms.DateInput(attrs={"type": "date"}),
            "actual_close_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pipeline"].queryset = Pipeline.objects.filter(
            is_active=True
        ).order_by("name")
        pipeline_id = None
        if self.instance and self.instance.pk and self.instance.pipeline_id:
            pipeline_id = self.instance.pipeline_id
        elif self.data.get("pipeline"):
            try:
                pipeline_id = int(self.data["pipeline"])
            except (TypeError, ValueError):
                pass
        if pipeline_id:
            self.fields["pipeline_stage"].queryset = PipelineStage.objects.filter(
                pipeline_id=pipeline_id
            ).order_by("order")
        else:
            default_pipeline = Pipeline.objects.filter(is_default=True).first()
            if default_pipeline:
                self.fields["pipeline_stage"].queryset = PipelineStage.objects.filter(
                    pipeline=default_pipeline
                ).order_by("order")
            else:
                self.fields["pipeline_stage"].queryset = PipelineStage.objects.order_by(
                    "pipeline", "order"
                )


class CSVImportForm(forms.Form):
    """Form for CSV import."""

    IMPORT_TYPE_CHOICES = [
        ("contacts", "Contacts Only"),
        ("companies", "Companies Only"),
        ("both", "Both Contacts and Companies"),
    ]

    csv_file = forms.FileField(
        label="CSV File",
        help_text="Upload a CSV file with contact and/or company data. The system will automatically detect and map columns.",
        widget=forms.FileInput(attrs={"accept": ".csv"}),
    )
    import_type = forms.ChoiceField(
        choices=IMPORT_TYPE_CHOICES,
        initial="both",
        label="Import Type",
        help_text="Select what to import from the CSV file",
    )
    create_companies = forms.BooleanField(
        required=False,
        initial=True,
        label="Create Companies",
        help_text="Automatically create companies if they don't exist when importing contacts",
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        label="Update Existing Records",
        help_text="Update existing contacts/companies if they already exist (matched by email for contacts, name for companies)",
    )


class ActivityForm(forms.ModelForm):
    """Form for logging communications / activities with leads."""

    class Meta:
        model = Activity
        fields = [
            "activity_type",
            "subject",
            "description",
            "link",
            "status",
            "contact",
            "company",
            "deal",
            "thread",
            "due_date",
            "duration_minutes",
            "outcome",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "outcome": forms.Textarea(attrs={"rows": 2}),
            "link": forms.URLInput(attrs={"placeholder": "https://..."}),
            "due_date": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make due_date accept browser datetime-local format
        self.fields["due_date"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        # Show only threads relevant to selected contact/company if bound data carries them
        # Otherwise show all threads for selection convenience.
        self.fields["thread"].queryset = ActivityThread.objects.all().order_by(
            "-updated_at"
        )


class SendEmailForm(forms.Form):
    """Form for composing and sending outbound emails to contacts."""

    subject = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Email subject"}),
    )
    body = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 10,
                "placeholder": "Write your message in Markdown...",
            }
        ),
        required=True,
    )
    schedule_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={"class": "form-control", "type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["schedule_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]


class WelcomeAutomationForm(forms.ModelForm):
    class Meta:
        model = WelcomeAutomation
        fields = ["name", "is_active", "enrollment_weight"]


class WelcomeEmailForm(forms.ModelForm):
    class Meta:
        model = WelcomeEmail
        fields = ["order", "offset_hours", "subject", "body"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 10}),
        }


class SequenceForm(forms.ModelForm):
    """Form for creating/editing messaging sequences."""

    class Meta:
        model = Sequence
        fields = ["name", "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


SequenceStepFormSet = inlineformset_factory(
    Sequence,
    SequenceStep,
    fields=["order", "offset_days", "activity_type", "auto_execute", "subject", "body"],
    extra=1,
    can_delete=True,
)


class SequenceEnrollContactsForm(forms.Form):
    """Form to add one or more contacts to a sequence."""

    contacts = forms.ModelMultipleChoiceField(
        queryset=Contact.objects.filter(is_active=True).order_by(
            "last_name", "first_name"
        ),
        widget=forms.SelectMultiple(attrs={"size": 12, "class": "form-select"}),
        required=True,
        help_text="Select one or more contacts to enroll in this sequence.",
    )


class EnrollContactInSequenceForm(forms.Form):
    """Form to enroll a single contact in a chosen sequence."""

    sequence = forms.ModelChoiceField(
        queryset=Sequence.objects.all().order_by("name"),
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
        empty_label="Choose a sequence…",
    )


OperatingAreaFormSet = inlineformset_factory(
    Company,
    OperatingArea,
    fields=["kind", "value", "code"],
    extra=1,
    can_delete=True,
)


class PainSignalForm(forms.ModelForm):
    """Form for creating/editing pain signals: detailed text + multi-select pain types."""

    class Meta:
        model = PainSignal
        fields = ["pain_signal", "pain_types", "url", "note", "observed_at"]
        widgets = {
            "pain_signal": forms.Textarea(
                attrs={
                    "rows": 4,
                    "maxlength": 1000,
                    "placeholder": "Detailed context for outreach (500–1000 chars)",
                }
            ),
            "pain_types": forms.SelectMultiple(attrs={"size": 7}),
            "url": forms.URLInput(attrs={"placeholder": "https://..."}),
            "note": forms.Textarea(attrs={"rows": 2}),
            "observed_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pain_types"].queryset = PainType.objects.order_by("name")
        self.fields["observed_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]


class SignalCreateForm(forms.Form):
    """Minimal form: URL only; LLM populates the rest."""

    source_url = forms.URLField(
        label="Source URL",
        max_length=2048,
        widget=forms.URLInput(attrs={"placeholder": "https://..."}),
        help_text="Paste a URL. The system will fetch the page and use an LLM (Ollama) to populate headline, summary, relevance, etc.",
    )


class SignalPasteForm(forms.Form):
    """Form shown when URL fetch fails (e.g. 403) or from direct "Paste page content" link."""

    source_url = forms.URLField(
        max_length=2048,
        required=False,
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://… (optional)"}),
    )
    pasted_content = forms.CharField(
        label="Pasted page content",
        widget=forms.Textarea(
            attrs={"rows": 12, "placeholder": "Paste the full page text here…"}
        ),
        help_text="Paste the article or page content you see in your browser. The LLM will extract headline, summary, relevance, etc.",
    )


class SignalForm(forms.ModelForm):
    """Form for editing a signal (all fields)."""

    class Meta:
        model = Signal
        fields = [
            "source_url",
            "headline",
            "date_logged",
            "week",
            "source_type",
            "relevance",
            "summary",
            "potential_action",
            "status",
            "linked_contact",
            "linked_company",
            "competitors",
            "competitors_notes",
        ]
        widgets = {
            "source_url": forms.URLInput(attrs={"placeholder": "https://..."}),
            "headline": forms.TextInput(attrs={"placeholder": "Headline / Key Point"}),
            "summary": forms.Textarea(attrs={"rows": 4}),
            "potential_action": forms.Textarea(attrs={"rows": 3}),
            "competitors": forms.Textarea(attrs={"rows": 2}),
            "competitors_notes": forms.Textarea(attrs={"rows": 4}),
            "date_logged": forms.DateInput(attrs={"type": "date"}),
        }


class NewsletterPlanForm(forms.ModelForm):
    """Form for creating and editing newsletter plans."""

    class Meta:
        model = NewsletterPlan
        fields = ["year", "name", "quarter_themes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. 2026 Newsletter Content"}),
            "quarter_themes": forms.HiddenInput(),
        }


class NewsletterEditionForm(forms.ModelForm):
    """Form for creating and editing newsletter editions."""

    class Meta:
        model = NewsletterEdition
        fields = [
            "plan",
            "quarter",
            "week_number",
            "day_of_week",
            "weekly_theme",
            "notes",
            "status",
            "subject",
            "body_html",
            "url",
        ]
        widgets = {
            "weekly_theme": forms.TextInput(attrs={"placeholder": "Weekly topic"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "subject": forms.TextInput(attrs={"placeholder": "Email subject line"}),
            "body_html": forms.Textarea(attrs={"rows": 12, "placeholder": "HTML or plain text content to send"}),
            "url": forms.URLInput(attrs={"placeholder": "https://..."}),
        }


class NewsletterAnalyticsForm(forms.ModelForm):
    """Form for editing newsletter analytics."""

    class Meta:
        model = NewsletterAnalytics
        fields = [
            "subscribers_count",
            "sent_count",
            "opens_count",
            "clicks_count",
            "ad_revenue",
            "unsubscribes_count",
            "bounces_count",
        ]


class NewsletterTemplateForm(forms.ModelForm):
    """Form for creating and editing newsletter templates (name only; sections in formset)."""

    class Meta:
        model = NewsletterTemplate
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": "e.g. Weekly digest"})}


class BaseNewsletterTemplateSectionFormSet(BaseInlineFormSet):
    """Formset that always returns template sections ordered by the order field."""

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.order_by("order")


NewsletterTemplateSectionFormSet = inlineformset_factory(
    NewsletterTemplate,
    NewsletterTemplateSection,
    fields=["order", "heading", "body_markdown"],
    extra=2,
    can_delete=True,
    formset=BaseNewsletterTemplateSectionFormSet,
    widgets={
        "heading": forms.TextInput(attrs={"placeholder": "Section heading", "class": "form-control"}),
        "body_markdown": forms.Textarea(attrs={"rows": 4, "placeholder": "Markdown content", "class": "form-control"}),
    },
)


class NewsletterIssueForm(forms.ModelForm):
    """Form for creating and editing newsletter issues (metadata; sections in formset)."""

    class Meta:
        model = NewsletterIssue
        fields = [
            "title",
            "slug",
            "subject",
            "preheader",
            "meta_title",
            "meta_description",
            "status",
            "scheduled_date",
            "divider_image_url",
            "created_from_template",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Issue title"}),
            "slug": forms.TextInput(attrs={"placeholder": "Optional; leave blank for draft and we'll generate one"}),
            "subject": forms.TextInput(attrs={"placeholder": "Email subject (defaults to title)"}),
            "preheader": forms.TextInput(attrs={"placeholder": "Optional preheader (shown next to subject)"}),
            "meta_title": forms.TextInput(attrs={"placeholder": "Meta title (max 60)", "maxlength": 60}),
            "meta_description": forms.Textarea(attrs={"rows": 2, "placeholder": "Meta description (max 320)", "maxlength": 320}),
            "scheduled_date": forms.DateInput(attrs={"type": "date"}),
            "divider_image_url": forms.URLInput(attrs={"placeholder": "Optional image URL between sections; leave blank for a line divider"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow saving drafts without a slug; view will auto-generate one when blank
        if not self.instance or not self.instance.pk:
            self.fields["slug"].required = False


class BaseNewsletterIssueSectionFormSet(BaseInlineFormSet):
    """Formset that yields forms sorted by the order field so the editor displays sections in Order order."""

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.order_by("order")

    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        # Allow empty extra forms (trailing rows) so save works with 0 or 1 section on create, and with empty rows on edit
        if i >= self.initial_form_count():
            form.empty_permitted = True
        return form

    def save_new_objects(self, commit=True):
        """Only save extra forms that have real content (heading or body). Empty trailing rows must not create sections."""
        self.new_objects = []
        for form in self.extra_forms:
            if not form.has_changed():
                continue
            if self.can_delete and self._should_delete_form(form):
                continue
            # Do not create a section when both heading and body are empty (avoids two new sections on every edit)
            cleaned = getattr(form, "cleaned_data", None) or {}
            heading = (cleaned.get("heading") or "").strip()
            body = (cleaned.get("body_markdown") or "").strip()
            if not heading and not body:
                continue
            self.new_objects.append(self.save_new(form, commit=commit))
            if not commit:
                self.saved_forms.append(form)
        return self.new_objects

    def __iter__(self):
        """Yield forms sorted by section order (existing sections by order field, then extra forms)."""
        def order_key(f):
            if f.instance and getattr(f.instance, "pk", None):
                return (0, getattr(f.instance, "order", 0), f.instance.pk)
            initial = getattr(f, "initial", None) or {}
            return (1, int(initial.get("order", 999)), id(f))
        yield from sorted(self.forms, key=order_key)


# Edit: no extra empty rows; use "Add section" to add more.
NewsletterIssueSectionFormSet = inlineformset_factory(
    NewsletterIssue,
    NewsletterIssueSection,
    fields=["order", "heading", "body_markdown"],
    extra=0,
    can_delete=True,
    formset=BaseNewsletterIssueSectionFormSet,
    widgets={
        "heading": forms.TextInput(attrs={"placeholder": "Section heading", "class": "form-control"}),
        "body_markdown": forms.Textarea(attrs={"rows": 4, "placeholder": "Markdown content", "class": "form-control"}),
    },
)

# Create: show 2 empty rows so user can add sections without clicking "Add section" first.
NewsletterIssueSectionFormSetForCreate = inlineformset_factory(
    NewsletterIssue,
    NewsletterIssueSection,
    fields=["order", "heading", "body_markdown"],
    extra=2,
    can_delete=True,
    formset=BaseNewsletterIssueSectionFormSet,
    widgets={
        "heading": forms.TextInput(attrs={"placeholder": "Section heading", "class": "form-control"}),
        "body_markdown": forms.Textarea(attrs={"rows": 4, "placeholder": "Markdown content", "class": "form-control"}),
    },
)
