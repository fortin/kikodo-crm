import uuid

from django.contrib.auth.models import User
from django.core.validators import EmailValidator, URLValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    """Abstract base class with self-updating created and modified fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Company(TimeStampedModel):
    """Company/Organization model"""

    name = models.CharField(max_length=255, unique=True)
    industry = models.CharField(max_length=100, blank=True)
    website = models.URLField(validators=[URLValidator()], blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(validators=[EmailValidator()], blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    annual_revenue = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    employee_count = models.PositiveIntegerField(null=True, blank=True)
    founded_year = models.IntegerField(
        null=True, blank=True, help_text="Year the company was founded"
    )
    size_category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Size category (e.g., '10000+', 'Self-employed')",
    )
    specialties = models.TextField(
        blank=True, help_text="Company specialties or focus areas"
    )
    logo_url = models.URLField(
        validators=[URLValidator()], blank=True, help_text="URL to company logo"
    )
    linkedin_url = models.URLField(
        validators=[URLValidator()], blank=True, help_text="LinkedIn company page URL"
    )
    icp_fit_score = models.PositiveIntegerField(
        default=0,
        help_text="ICP fit score from 0 (poor fit) to 100 (excellent fit)",
    )
    icp_fit_tier = models.CharField(
        max_length=1,
        blank=True,
        help_text="Simple ICP tier label derived from the fit score (e.g. A, B, C, D)",
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_companies",
    )
    is_active = models.BooleanField(default=True)
    competitor = models.BooleanField(
        default=False, help_text="Mark this company as a competitor"
    )

    # Prospecting
    facility_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of facilities (e.g. 3–15 ideal for LTC)",
    )
    priority_tier = models.IntegerField(
        null=True,
        blank=True,
        choices=[(1, "Tier 1"), (2, "Tier 2"), (3, "Tier 3")],
        help_text="Priority tier 1, 2, or 3",
    )

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("crm:company_detail", kwargs={"pk": self.pk})

    @property
    def full_address(self):
        """Return formatted full address"""
        parts = [self.address, self.city, self.state, self.country, self.postal_code]
        return ", ".join(filter(None, parts))


class OperatingArea(TimeStampedModel):
    """Where a company operates (state, province, region, country). General-purpose, not US-only."""

    KIND_CHOICES = [
        ("state", "State"),
        ("province", "Province"),
        ("region", "Region"),
        ("country", "Country"),
        ("other", "Other"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="operating_areas",
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="state")
    value = models.CharField(max_length=100, help_text="e.g. CA, Ontario, Bavaria")
    code = models.CharField(max_length=50, blank=True, help_text="Optional short code")

    class Meta:
        ordering = ["kind", "value"]
        verbose_name_plural = "Operating areas"

    def __str__(self):
        return f"{self.get_kind_display()}: {self.value}"


class Contact(TimeStampedModel):
    """Contact/Person model"""

    SALUTATION_CHOICES = [
        ("Mr.", "Mr."),
        ("Mrs.", "Mrs."),
        ("Ms.", "Ms."),
        ("Dr.", "Dr."),
        ("Prof.", "Prof."),
    ]

    CONTACT_STATUS_CHOICES = [
        ("lead", "Lead"),
        ("prospect", "Prospect"),
        ("customer", "Customer"),
        ("inactive", "Inactive"),
    ]

    # Basic Information
    salutation = models.CharField(max_length=10, choices=SALUTATION_CHOICES, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(
        validators=[EmailValidator()], unique=True, blank=True, null=True
    )
    phone = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)

    # Professional Information
    job_title = models.CharField(max_length=500, blank=True)
    department = models.CharField(max_length=100, blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contacts",
    )

    # Address Information
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=100, blank=True)

    # CRM Information
    status = models.CharField(
        max_length=20, choices=CONTACT_STATUS_CHOICES, default="lead"
    )
    outreach_status = models.CharField(
        max_length=32,
        choices=[
            ("not_contacted", "Not contacted"),
            ("reached_out", "Reached out"),
            ("responded", "Responded"),
            ("bounced", "Bounced"),
            ("not_a_fit", "Not a fit"),
        ],
        default="not_contacted",
        help_text="Outreach stage for this contact",
    )
    source = models.CharField(max_length=100, blank=True)  # How they found us
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_contacts",
    )
    is_active = models.BooleanField(default=True)
    last_contact = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time we contacted or heard from this lead",
    )
    verified = models.BooleanField(
        default=False,
        help_text="Contact has been verified (e.g. email/LinkedIn confirmed)",
    )

    # Consent & communication preferences
    can_email_outbound = models.BooleanField(
        default=True,
        help_text="Allow one-to-one and sequence emails to this contact",
    )
    can_call = models.BooleanField(
        default=True,
        help_text="Allow phone calls to this contact",
    )
    can_linkedin = models.BooleanField(
        default=True,
        help_text="Allow LinkedIn and social outreach to this contact",
    )
    can_marketing_email = models.BooleanField(
        default=True,
        help_text="Allow bulk/marketing emails to this contact",
    )
    newsletter_subscribed = models.BooleanField(
        default=False,
        help_text="Subscribed to the newsletter; gates sending of scheduled newsletter and welcome series.",
    )

    # Social Media
    linkedin = models.URLField(blank=True, help_text="LinkedIn profile URL")
    linkedin_url = models.URLField(blank=True)  # Deprecated: use linkedin instead
    twitter_handle = models.CharField(max_length=50, blank=True)

    # Additional Information
    headline = models.CharField(
        max_length=500, blank=True, help_text="Professional headline or tagline"
    )
    bio = models.TextField(blank=True, help_text="Biography or about section")
    skills = models.TextField(blank=True, help_text="Skills or competencies")
    birthday = models.DateField(null=True, blank=True, help_text="Date of birth")
    pronouns = models.CharField(
        max_length=50, blank=True, help_text="Preferred pronouns"
    )
    latest_post = models.DateTimeField(
        null=True, blank=True, help_text="Date and time of latest social media post"
    )

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_address(self):
        """Return formatted full address"""
        parts = [self.address, self.city, self.state, self.country, self.postal_code]
        return ", ".join(filter(None, parts))

    def get_absolute_url(self):
        return reverse("crm:contact_detail", kwargs={"pk": self.pk})


class PainType(TimeStampedModel):
    """Categorization for pain signals (multi-select per signal)."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PainSignal(TimeStampedModel):
    """Log of pain/signal per company/contact: detailed text + optional types for filtering."""

    # Legacy single-type (kept for backward compat; prefer pain_types)
    SIGNAL_TYPE_CHOICES = [
        ("job_posting", "Job posting"),
        ("glassdoor", "Glassdoor"),
        ("news", "News mention"),
        ("other", "Other"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="pain_signals",
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="pain_signals",
    )
    # Detailed context for outreach (500–1000 chars recommended; enforced in form)
    pain_signal = models.TextField(blank=True)
    # Multi-select categorization for filtering
    pain_types = models.ManyToManyField(
        PainType,
        related_name="pain_signals",
        blank=True,
    )
    signal_type = models.CharField(
        max_length=20,
        choices=SIGNAL_TYPE_CHOICES,
        default="other",
        blank=True,
        help_text="Legacy; prefer pain_types",
    )
    url = models.URLField(blank=True)
    note = models.TextField(blank=True)
    observed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-observed_at", "-created_at"]
        verbose_name_plural = "Pain signals"

    def __str__(self):
        types_display = ", ".join(pt.name for pt in self.pain_types.all()[:3])
        if types_display:
            return f"{types_display} @ {self.company.name}"
        return f"{self.get_signal_type_display()} @ {self.company.name}"


class Signal(TimeStampedModel):
    """
    Market/source signal: URL + LLM-populated fields matching the Signals-Grid spreadsheet.
    Minimal input: source_url; LLM fills headline, source_type, relevance, summary, etc.
    """

    SOURCE_TYPE_CHOICES = [
        ("publisher_news", "Publisher News"),
        ("general_market", "General Market Signal"),
        ("compliance_update", "Compliance Update"),
        ("thought_leadership", "Thought leadership / Trend article"),
        ("market_forecast", "Market Trend / Industry Forecast"),
        ("regulatory", "Regulatory update / analysis"),
        ("potential_lead", "Potential Lead"),
        ("other", "Other"),
    ]

    RELEVANCE_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    STATUS_CHOICES = [
        ("logged", "Logged"),
        ("follow_up", "Follow up"),
        ("done", "Done"),
    ]

    # Minimal input
    source_url = models.URLField(
        max_length=2048,
        help_text="Source URL; LLM will read and populate fields below.",
    )

    # LLM-populated / editable (Signals-Grid columns)
    headline = models.CharField(
        max_length=500,
        blank=True,
        help_text="Headline / Key Point",
    )
    date_logged = models.DateField(
        default=timezone.now,
        help_text="Date logged",
    )
    week = models.CharField(
        max_length=20,
        blank=True,
        help_text="Week label (e.g. 2025-W40)",
    )
    source_type = models.CharField(
        max_length=40,
        choices=SOURCE_TYPE_CHOICES,
        default="other",
        blank=True,
    )
    relevance = models.CharField(
        max_length=10,
        choices=RELEVANCE_CHOICES,
        default="medium",
        blank=True,
    )
    summary = models.TextField(blank=True)
    potential_action = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="logged",
    )

    # Optional links to CRM entities
    linked_contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signals",
    )
    linked_company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signals",
    )

    # Competitor / positioning notes (from CSV)
    competitors = models.TextField(
        blank=True,
        help_text="Competitors or companies mentioned",
    )
    competitors_notes = models.TextField(
        blank=True,
        help_text="Primary audience, content focus, relevance to ICP, notes/positioning",
    )

    class Meta:
        ordering = ["-date_logged", "-created_at"]
        verbose_name_plural = "Signals"

    def __str__(self):
        return self.headline or self.source_url[:60]

    def get_absolute_url(self):
        return reverse("crm:signal_detail", kwargs={"pk": self.pk})


class Deal(TimeStampedModel):
    """Deal/Opportunity model"""

    STAGE_CHOICES = [
        ("prospecting", "Prospecting"),
        ("qualification", "Qualification"),
        ("proposal", "Proposal"),
        ("negotiation", "Negotiation"),
        ("closed_won", "Closed Won"),
        ("closed_lost", "Closed Lost"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default="prospecting",
        blank=True,
        help_text="Legacy; use pipeline_stage when set.",
    )
    probability = models.PositiveIntegerField(
        default=0, help_text="Probability percentage (0-100)"
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )

    # Configurable pipeline (enterprise)
    pipeline = models.ForeignKey(
        "Pipeline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deals",
    )
    pipeline_stage = models.ForeignKey(
        "PipelineStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deals",
    )

    # Relationships
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="deals")
    company = models.ForeignKey(
        Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="deals"
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_deals",
    )

    # Dates
    expected_close_date = models.DateField()
    actual_close_date = models.DateField(null=True, blank=True)

    # Additional fields
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-expected_close_date"]

    def __str__(self):
        return f"{self.name} - ${self.amount}"

    def save(self, *args, **kwargs):
        if (
            self.pipeline_stage_id
            and hasattr(self, "pipeline_stage")
            and self.pipeline_stage
        ):
            if self.pipeline_stage.is_closed:
                self.stage = (
                    "closed_won" if self.pipeline_stage.is_won else "closed_lost"
                )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("crm:deal_detail", kwargs={"pk": self.pk})

    @property
    def weighted_amount(self):
        """Calculate weighted deal amount based on probability"""
        return self.amount * (self.probability / 100)

    @property
    def stage_display(self):
        """Stage name for display: pipeline_stage if set, else legacy stage."""
        if self.pipeline_stage_id:
            return self.pipeline_stage.name
        return self.get_stage_display()

    @property
    def days_to_close(self):
        """Calculate days until expected close date"""
        if self.expected_close_date:
            delta = self.expected_close_date - timezone.now().date()
            return delta.days
        return None


class Activity(TimeStampedModel):
    """Activity/Task model for tracking interactions"""

    ACTIVITY_TYPES = [
        ("call", "Phone Call"),
        ("email", "Email"),
        ("meeting", "Meeting"),
        ("task", "Task"),
        ("note", "Note"),
        ("demo", "Demo"),
        ("proposal", "Proposal"),
        ("linkedin", "LinkedIn"),
        ("system", "System"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("system", "System"),
    ]

    TASK_PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    CALL_OUTCOME_CHOICES = [
        ("no_answer", "No answer"),
        ("left_voicemail", "Left voicemail"),
        ("connected_interested", "Connected - interested"),
        ("connected_not_interested", "Connected - not interested"),
        ("wrong_number", "Wrong number"),
        ("scheduled_followup", "Scheduled follow-up"),
        ("other", "Other"),
    ]

    MEETING_TYPE_CHOICES = [
        ("discovery", "Discovery"),
        ("demo", "Demo"),
        ("renewal", "Renewal"),
        ("qbr", "QBR"),
        ("other", "Other"),
    ]

    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        default="outbound",
        help_text="Direction of the activity (inbound, outbound, or system-generated)",
    )
    subject = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    link = models.URLField(
        blank=True,
        help_text="Link to the message (email thread, LinkedIn conversation, etc.)",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_pinned = models.BooleanField(
        default=False,
        help_text="Pinned activities are shown at the top of timelines",
    )

    # Threading
    thread = models.ForeignKey(
        "ActivityThread",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
        help_text="Optional thread to group related messages",
    )

    # Relationships
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="activities",
        null=True,
        blank=True,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="activities",
        null=True,
        blank=True,
    )
    deal = models.ForeignKey(
        Deal, on_delete=models.CASCADE, related_name="activities", null=True, blank=True
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_activities",
    )

    # Scheduling
    due_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)

    # Additional fields
    duration_minutes = models.PositiveIntegerField(
        null=True, blank=True, help_text="Duration in minutes"
    )
    outcome = models.TextField(
        blank=True, help_text="Result or outcome of the activity"
    )

    # Email-specific metadata
    delivery_status = models.CharField(
        max_length=20,
        blank=True,
        help_text="Delivery status for email activities (e.g. queued, sent, bounced)",
    )
    opens_count = models.PositiveIntegerField(
        default=0, help_text="Number of times an email activity was opened"
    )
    clicks_count = models.PositiveIntegerField(
        default=0, help_text="Number of times links in an email activity were clicked"
    )
    last_opened_at = models.DateTimeField(null=True, blank=True)
    last_clicked_at = models.DateTimeField(null=True, blank=True)
    external_message_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Identifier from the external email provider, if applicable",
    )

    # Call-specific metadata
    call_outcome = models.CharField(
        max_length=50,
        blank=True,
        choices=CALL_OUTCOME_CHOICES,
        help_text="Structured outcome for call activities",
    )
    duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration of the call in seconds (for call activities)",
    )
    recording_url = models.URLField(
        blank=True,
        help_text="URL to call recording, if available",
    )
    transcript = models.TextField(
        blank=True,
        help_text="Optional transcript or notes from the call recording",
    )
    phone_number_used = models.CharField(
        max_length=50,
        blank=True,
        help_text="Phone number used for the call (dialer/rep number)",
    )

    # Task/LinkedIn/other action metadata
    task_type = models.CharField(
        max_length=50,
        blank=True,
        help_text=(
            "Optional fine-grained task type, e.g. "
            '"LINKEDIN_VIEW_PROFILE", "FOLLOWUP", "MEETING_PREP"'
        ),
    )
    task_priority = models.CharField(
        max_length=10,
        choices=TASK_PRIORITY_CHOICES,
        default="medium",
        help_text="Priority for task-type activities",
    )

    # Meeting metadata
    meeting_type = models.CharField(
        max_length=50,
        blank=True,
        choices=MEETING_TYPE_CHOICES,
        help_text="Categorization for meeting-type activities",
    )
    start_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start time for meeting-type activities, if different from due date",
    )
    end_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End time for meeting-type activities",
    )
    location_url = models.URLField(
        blank=True,
        help_text="Meeting location or conferencing link (e.g. Zoom, Google Meet)",
    )

    # Sequence associations
    sequence_step = models.ForeignKey(
        "SequenceStep",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_activities",
        help_text="Sequence step that generated this activity, if any",
    )
    sequence_enrollment = models.ForeignKey(
        "SequenceEnrollment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
        help_text="Sequence enrollment associated with this activity, if any",
    )

    class Meta:
        verbose_name_plural = "Activities"
        ordering = ["-due_date", "-created_at"]

    def __str__(self):
        return f"{self.get_activity_type_display()}: {self.subject}"

    def get_absolute_url(self):
        return reverse("crm:activity_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if self.status == "sent" and not self.completed_date:
            self.completed_date = timezone.now()
        super().save(*args, **kwargs)

        # Update contact.last_contact when we log or complete an activity
        # Use completed_date if present, otherwise due_date, otherwise now.
        ts = self.completed_date or self.due_date or timezone.now()
        if self.contact:
            if not self.contact.last_contact or ts > self.contact.last_contact:
                Contact.objects.filter(pk=self.contact.pk).update(last_contact=ts)


class ActivityThread(TimeStampedModel):
    """Grouping for related activities/messages (conversation thread)."""

    subject = models.CharField(max_length=255, blank=True)
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, null=True, blank=True, related_name="threads"
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name="threads"
    )
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="threads"
    )

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.subject or f"Thread #{self.pk}"


class Sequence(TimeStampedModel):
    """Messaging sequence template for planning outreach to leads."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_sequences",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Legacy flag; prefer using status going forward",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Lifecycle status of this sequence",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class SequenceStep(TimeStampedModel):
    """Single step in a messaging sequence (e.g. Day 0 email, Day 3 follow‑up)."""

    sequence = models.ForeignKey(
        Sequence, on_delete=models.CASCADE, related_name="steps"
    )
    order = models.PositiveIntegerField(help_text="Order of this step in the sequence")
    offset_days = models.PositiveIntegerField(
        default=0,
        help_text="Days after previous step to schedule this step (0 = same day)",
    )
    activity_type = models.CharField(
        max_length=20, choices=Activity.ACTIVITY_TYPES, default="email"
    )
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    auto_execute = models.BooleanField(
        default=True,
        help_text=(
            "If enabled, the step will execute automatically (e.g. send email). "
            "If disabled, a task will be created for a human to complete."
        ),
    )

    class Meta:
        ordering = ["sequence", "order"]
        unique_together = ["sequence", "order"]

    def __str__(self) -> str:
        return f"{self.sequence.name} - Step {self.order}"


class SequenceEnrollment(TimeStampedModel):
    """Enrollment of a contact (and optional deal) into a sequence."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("stopped_on_reply", "Stopped on reply"),
        ("unsubscribed", "Unsubscribed"),
        ("paused", "Paused"),
    ]

    sequence = models.ForeignKey(
        Sequence, on_delete=models.CASCADE, related_name="enrollments"
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="sequence_enrollments"
    )
    deal = models.ForeignKey(
        Deal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sequence_enrollments",
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sequence_enrollments",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Current state of this enrollment within the sequence",
    )
    current_step_index = models.PositiveIntegerField(
        default=0,
        help_text="Zero-based index of the next step to execute",
    )
    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the next step should be executed",
    )
    last_executed_step = models.ForeignKey(
        SequenceStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Last step that was executed for this enrollment",
    )

    class Meta:
        ordering = ["-next_run_at", "-created_at"]

    def __str__(self) -> str:
        return f"{self.sequence.name} → {self.contact.full_name}"


class Tag(TimeStampedModel):
    """Tag model for categorizing contacts, companies, and deals"""

    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(
        max_length=7, default="#007bff", help_text="Hex color code"
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ContactTag(models.Model):
    """Many-to-many relationship between Contact and Tag"""

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["contact", "tag"]


class CompanyTag(models.Model):
    """Many-to-many relationship between Company and Tag"""

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["company", "tag"]


class DealTag(models.Model):
    """Many-to-many relationship between Deal and Tag"""

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["deal", "tag"]


class Pipeline(TimeStampedModel):
    """Sales pipeline configuration"""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PipelineStage(TimeStampedModel):
    """Pipeline stages configuration"""

    pipeline = models.ForeignKey(
        Pipeline, on_delete=models.CASCADE, related_name="stages"
    )
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField()
    probability = models.PositiveIntegerField(
        default=0, help_text="Default probability percentage"
    )
    is_closed = models.BooleanField(default=False, help_text="Is this a closed stage?")
    is_won = models.BooleanField(default=False, help_text="Is this a won stage?")

    class Meta:
        ordering = ["pipeline", "order"]
        unique_together = ["pipeline", "order"]

    def __str__(self):
        return f"{self.pipeline.name} - {self.name}"


class AuditLog(TimeStampedModel):
    """Audit log for create/update/delete on key CRM entities."""

    ACTION_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True)
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit log entry"
        verbose_name_plural = "Audit log"

    def __str__(self):
        return f"{self.action} {self.model_name}#{self.object_id} by {self.user_id}"


class Team(TimeStampedModel):
    """Sales team for grouping users and record visibility."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserProfile(TimeStampedModel):
    """Extended user profile: team membership and role (via Django Group)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    email_signature = models.TextField(
        blank=True,
        help_text="HTML signature for outgoing emails (per-user; falls back to EMAIL_SIGNATURE_HTML if empty)",
    )

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.team.name if self.team else 'No team'})"


class Webhook(TimeStampedModel):
    """Outbound webhook: POST to URL on entity create/update/delete with HMAC-signed payload."""

    EVENT_CHOICES = [
        ("contact.create", "Contact created"),
        ("contact.update", "Contact updated"),
        ("contact.delete", "Contact deleted"),
        ("company.create", "Company created"),
        ("company.update", "Company updated"),
        ("company.delete", "Company deleted"),
        ("deal.create", "Deal created"),
        ("deal.update", "Deal updated"),
        ("deal.delete", "Deal deleted"),
        ("activity.create", "Activity created"),
        ("activity.update", "Activity updated"),
        ("activity.delete", "Activity deleted"),
    ]

    name = models.CharField(max_length=100, help_text="Label for this webhook")
    url = models.URLField(max_length=2048, help_text="Endpoint URL to POST")
    secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secret for HMAC-SHA256 X-Webhook-Signature header",
    )
    events = models.JSONField(
        default=list,
        help_text="List of event names, e.g. ['contact.create', 'contact.update']",
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class NewsletterPlan(TimeStampedModel):
    """Annual newsletter plan with quarterly themes."""

    year = models.IntegerField(help_text="Plan year (e.g. 2026)")
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional plan name (e.g. 2026 Newsletter Content)",
    )
    quarter_themes = models.JSONField(
        default=dict,
        blank=True,
        help_text='Quarter themes, e.g. {"Q1": "Theme A", "Q2": "Theme B"}',
    )

    class Meta:
        ordering = ["-year"]
        unique_together = ["year"]
        verbose_name = "Newsletter plan"
        verbose_name_plural = "Newsletter plans"

    def __str__(self):
        return self.name or f"Newsletter Plan {self.year}"


class NewsletterEdition(TimeStampedModel):
    """Individual newsletter edition (week or day row in the annual plan)."""

    STATUS_CHOICES = [
        ("drafting", "Drafting"),
        ("scheduled", "Scheduled"),
        ("published", "Published"),
        ("cancelled", "Cancelled"),
    ]

    DAY_OF_WEEK_CHOICES = [
        ("Monday", "Monday"),
        ("Tuesday", "Tuesday"),
        ("Wednesday", "Wednesday"),
        ("Thursday", "Thursday"),
        ("Friday", "Friday"),
        ("Saturday", "Saturday"),
        ("Sunday", "Sunday"),
    ]

    plan = models.ForeignKey(
        NewsletterPlan,
        on_delete=models.CASCADE,
        related_name="editions",
    )
    quarter = models.CharField(max_length=2, choices=[("Q1", "Q1"), ("Q2", "Q2"), ("Q3", "Q3"), ("Q4", "Q4")])
    week_number = models.PositiveIntegerField(help_text="Week number (1-52)")
    day_of_week = models.CharField(
        max_length=10,
        choices=DAY_OF_WEEK_CHOICES,
        blank=True,
        default="Monday",
        help_text="Day of week; date is derived from week_number + day_of_week",
    )
    weekly_theme = models.CharField(
        max_length=500,
        blank=True,
        help_text="Weekly topic for this week",
    )
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="drafting",
    )
    subject = models.CharField(
        max_length=500,
        blank=True,
        help_text="Email subject line for this edition",
    )
    body_html = models.TextField(
        blank=True,
        help_text="HTML or plain text content of the newsletter to send",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this edition was sent to subscribers; null means not yet sent",
    )
    url = models.URLField(
        blank=True,
        help_text="Link to published newsletter",
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="newsletter_editions",
    )

    class Meta:
        ordering = ["plan", "quarter", "week_number", "day_of_week"]
        verbose_name = "Newsletter edition"
        verbose_name_plural = "Newsletter editions"

    @staticmethod
    def _quarter_from_date(d):
        """Return Q1/Q2/Q3/Q4 from a date's month."""
        if d is None:
            return "Q1"
        month = d.month
        if month <= 3:
            return "Q1"
        if month <= 6:
            return "Q2"
        if month <= 9:
            return "Q3"
        return "Q4"

    @property
    def scheduled_date(self):
        """Date derived from plan year, week_number, and day_of_week.
        Week 1 = first Monday of the year (matches common editorial calendars, not ISO 8601).
        """
        from datetime import timedelta

        year = self.plan.year if self.plan_id else timezone.now().year
        jan1 = timezone.datetime(year, 1, 1).date()
        # First Monday of year: weekday() 0=Mon, 6=Sun
        days_until_monday = (7 - jan1.weekday()) % 7
        first_monday = jan1 + timedelta(days=days_until_monday)
        # Week N Monday = first_monday + (N-1)*7
        week_monday = first_monday + timedelta(days=(self.week_number - 1) * 7)
        day_name = self.day_of_week or "Monday"
        day_offset = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6,
        }.get(day_name, 0)
        return week_monday + timedelta(days=day_offset)

    def save(self, *args, **kwargs):
        """Auto-set quarter from scheduled_date before save."""
        if self.plan_id and self.week_number:
            sd = self.scheduled_date
            self.quarter = self._quarter_from_date(sd)
        super().save(*args, **kwargs)

    def __str__(self):
        label = self.weekly_theme or "(no theme)"
        return f"{self.plan.year} {self.quarter} W{self.week_number} - {label}"

    def get_absolute_url(self):
        return reverse("crm:newsletter_edition_detail", kwargs={"pk": self.pk})


class NewsletterAnalytics(TimeStampedModel):
    """Per-edition analytics: subscribers, opens, ad revenue, etc."""

    edition = models.OneToOneField(
        NewsletterEdition,
        on_delete=models.CASCADE,
        related_name="analytics",
    )
    subscribers_count = models.PositiveIntegerField(
        default=0,
        help_text="Subscriber count at send time",
    )
    sent_count = models.PositiveIntegerField(default=0)
    opens_count = models.PositiveIntegerField(
        default=0,
        help_text="Readers / unique opens",
    )
    clicks_count = models.PositiveIntegerField(default=0)
    ad_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Ad revenue from this edition",
    )
    unsubscribes_count = models.PositiveIntegerField(default=0)
    bounces_count = models.PositiveIntegerField(default=0)
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last sync from ESP (Mailchimp, Beehiiv, etc.)",
    )

    class Meta:
        verbose_name = "Newsletter analytics"
        verbose_name_plural = "Newsletter analytics"

    def __str__(self):
        return f"Analytics for {self.edition}"


class NewsletterConversion(TimeStampedModel):
    """Deal attribution: link a deal to a newsletter edition."""

    ATTRIBUTION_CHOICES = [
        ("lead", "Lead"),
        ("opportunity", "Opportunity"),
        ("closed_won", "Closed Won"),
    ]

    edition = models.ForeignKey(
        NewsletterEdition,
        on_delete=models.CASCADE,
        related_name="conversions",
    )
    deal = models.ForeignKey(
        Deal,
        on_delete=models.CASCADE,
        related_name="newsletter_conversions",
    )
    attribution_type = models.CharField(
        max_length=20,
        choices=ATTRIBUTION_CHOICES,
        default="lead",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Newsletter conversion"
        verbose_name_plural = "Newsletter conversions"
        unique_together = ["edition", "deal"]

    def __str__(self):
        return f"{self.edition} → {self.deal.name}"


class WelcomeAutomation(TimeStampedModel):
    """Welcome email sequence. New subscribers are assigned using weighted random among active automations (A/B tests)."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(
        max_length=64,
        unique=True,
        blank=True,
        help_text="Stable id; auto-generated from name when left blank.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive automations are not assigned to new subscribers.",
    )
    enrollment_weight = models.PositiveIntegerField(
        default=1,
        help_text="Relative chance this automation is chosen among active ones (e.g. 1 and 1 → 50/50).",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Welcome automation"
        verbose_name_plural = "Welcome automations"

    def save(self, *args, **kwargs):
        if not (self.slug or "").strip():
            base = slugify(self.name)[:60] or "automation"
            candidate = base
            n = 1
            while WelcomeAutomation.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                n += 1
                candidate = f"{base}-{n}"
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class WelcomeEmail(TimeStampedModel):
    """One step in a welcome automation."""

    automation = models.ForeignKey(
        WelcomeAutomation,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    order = models.PositiveIntegerField(
        help_text="Step order (1 = first at signup; then offset_hours after each prior send)",
    )
    subject = models.CharField(max_length=500)
    body = models.TextField(
        blank=True,
        help_text="Plain text or HTML body for this welcome email",
    )
    offset_hours = models.PositiveIntegerField(
        default=0,
        help_text="Hours after previous step to send (0 = at signup for step 1)",
    )

    class Meta:
        ordering = ["automation", "order"]
        verbose_name = "Welcome email step"
        verbose_name_plural = "Welcome email steps"
        constraints = [
            models.UniqueConstraint(
                fields=["automation", "order"],
                name="crm_welcomeemail_automation_order_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.automation.name} step {self.order}: {self.subject}"


class WelcomeEnrollment(TimeStampedModel):
    """Enrollment of a contact in the welcome email series."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="welcome_enrollments",
    )
    automation = models.ForeignKey(
        WelcomeAutomation,
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    enrolled_at = models.DateTimeField(default=timezone.now)
    current_step_index = models.PositiveIntegerField(
        default=0,
        help_text="Zero-based index of the next step to send",
    )
    next_send_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to send the next welcome email",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    class Meta:
        ordering = ["-enrolled_at"]
        verbose_name = "Welcome enrollment"
        verbose_name_plural = "Welcome enrollments"

    def __str__(self):
        return f"Welcome → {self.contact.full_name}"


class NewsletterTemplate(TimeStampedModel):
    """Reusable newsletter structure: named template with ordered sections (heading + Markdown body)."""

    name = models.CharField(max_length=255, help_text="Template name for reuse")

    class Meta:
        ordering = ["name"]
        verbose_name = "Newsletter template"
        verbose_name_plural = "Newsletter templates"

    def __str__(self):
        return self.name


class NewsletterTemplateSection(TimeStampedModel):
    """One section in a newsletter template: heading + Markdown body."""

    template = models.ForeignKey(
        NewsletterTemplate,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    heading = models.CharField(max_length=500)
    body_markdown = models.TextField(
        blank=True,
        help_text="Markdown-formatted body for this section",
    )

    class Meta:
        ordering = ["template", "order"]
        verbose_name = "Newsletter template section"
        verbose_name_plural = "Newsletter template sections"

    def __str__(self):
        return self.heading or f"Section {self.order}"


class NewsletterIssue(TimeStampedModel):
    """A single newsletter issue (structured with sections). Can be created from a template. When published, emails are sent and a blog post is created on kikodo.app."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("published", "Published"),
    ]

    title = models.CharField(max_length=500, help_text="Issue title (and blog post title)")
    slug = models.SlugField(
        max_length=500,
        unique=True,
        help_text="URL slug for the blog post (e.g. newsletter-2025-01-15)",
    )
    subject = models.CharField(
        max_length=500,
        blank=True,
        help_text="Email subject line (defaults to title if empty)",
    )
    preheader = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional email preheader/preview text shown by many inboxes (hidden in the HTML body).",
    )
    meta_title = models.CharField(
        max_length=60,
        blank=True,
        help_text="Optional meta title for blog (max 60 chars)",
    )
    meta_description = models.CharField(
        max_length=320,
        blank=True,
        help_text="Optional meta description for blog (max 320 chars)",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    scheduled_date = models.DateField(
        null=True,
        blank=True,
        help_text="Optional scheduled date (for display/filtering)",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When newsletter emails were sent",
    )
    blog_published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the post was published on www.kikodo.app",
    )
    created_from_template = models.ForeignKey(
        NewsletterTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issues_created",
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="newsletter_issues",
    )
    edition = models.ForeignKey(
        NewsletterEdition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issues",
        help_text="Link to the plan edition this issue corresponds to (if created from plan).",
    )
    divider_image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Optional image URL to show between sections. If empty, a simple line divider is used.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Newsletter issue"
        verbose_name_plural = "Newsletter issues"

    def __str__(self):
        return self.title or self.slug

    def get_absolute_url(self):
        return reverse("crm:newsletter_issue_detail", kwargs={"pk": self.pk})

    def render_body_html(self):
        """Render all sections to a single HTML string (Markdown converted, sections wrapped with headings).
        Between sections: if divider_image_url is set, insert that image; otherwise use HTML hr divider.
        No divider between the first and second sections (e.g. banner + intro flow together).
        """
        import markdown
        from html import escape
        import re

        sections = list(self.sections.order_by("order"))
        parts = []
        for i, sec in enumerate(sections):
            html = markdown.markdown(sec.body_markdown or "", extensions=["nl2br"])
            heading_html = f"<h2>{sec.heading}</h2>\n" if sec.heading else ""
            block = f"{heading_html}{html}"
            if i == 0:
                block = f'<div class="newsletter-section-first">{block}</div>'
            parts.append(block)
            # Skip divider after first section only (between section 1 and 2)
            if i < len(sections) - 1 and i != 0:
                if self.divider_image_url:
                    url = escape(self.divider_image_url)
                    parts.append(
                        f'<div class="newsletter-divider">'
                        f'<img src="{url}" alt="" style="max-width:100%;height:auto;display:block;" />'
                        f'</div>'
                    )
                else:
                    parts.append('<hr class="newsletter-divider-hr" />')
        full_html = "\n\n".join(parts) if parts else ""

        # Email clients (and some ESPs) sometimes rewrite images to full width.
        # Force the Compliance Unlock logo banner to a reasonable fixed display width
        # (can shrink on mobile, but won't scale up to the container width).
        if full_html:
            def _force_logo_banner(match: re.Match) -> str:
                src = match.group("src")
                alt = match.group("alt") or "The Compliance Unlock"
                # 420px keeps the banner from looking "full width" in a 600px email container.
                # Use !important to beat common client rewriters.
                return (
                    f'<img src="{src}" alt="{alt}" width="420" '
                    f'style="width:420px !important; max-width:100% !important; '
                    f'height:auto !important; display:block; margin:0 auto;" />'
                )

            full_html = re.sub(
                r"""<img\b[^>]*\bsrc=(?P<q>["'])(?P<src>[^"']*compliance-unlock-logo\.png)(?P=q)[^>]*?(?:\balt=(?P<aq>["'])(?P<alt>[^"']*)(?P=aq))?[^>]*>""",
                _force_logo_banner,
                full_html,
                count=1,
                flags=re.IGNORECASE,
            )

        return full_html


class NewsletterIssueSection(TimeStampedModel):
    """One section in a newsletter issue: heading + Markdown body."""

    issue = models.ForeignKey(
        NewsletterIssue,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    heading = models.CharField(max_length=500, blank=True)
    body_markdown = models.TextField(
        blank=True,
        help_text="Markdown-formatted body for this section",
    )

    class Meta:
        ordering = ["issue", "order"]
        verbose_name = "Newsletter issue section"
        verbose_name_plural = "Newsletter issue sections"

    def __str__(self):
        return self.heading or f"Section {self.order}"
