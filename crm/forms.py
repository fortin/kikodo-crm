from django import forms
from django.forms import inlineformset_factory

from .models import (
    Activity,
    ActivityThread,
    Company,
    Contact,
    Deal,
    OperatingArea,
    PainSignal,
    PainType,
    Pipeline,
    PipelineStage,
    Sequence,
    SequenceStep,
    Signal,
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
    """Form shown when URL fetch fails (e.g. 403): paste page content, LLM fills fields."""

    source_url = forms.URLField(max_length=2048, widget=forms.HiddenInput())
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
