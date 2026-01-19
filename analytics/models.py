from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone

from crm.models import Activity, Company, Contact, Deal, TimeStampedModel


class DashboardWidget(TimeStampedModel):
    """Dashboard widget configuration"""

    WIDGET_TYPES = [
        ("chart", "Chart"),
        ("metric", "Metric"),
        ("table", "Table"),
        ("list", "List"),
    ]

    name = models.CharField(max_length=100)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    description = models.TextField(blank=True)
    config = models.JSONField(default=dict, help_text="Widget configuration data")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="dashboard_widgets"
    )

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class Report(TimeStampedModel):
    """Saved reports configuration"""

    REPORT_TYPES = [
        ("contacts", "Contacts"),
        ("companies", "Companies"),
        ("deals", "Deals"),
        ("activities", "Activities"),
        ("sales", "Sales Performance"),
        ("pipeline", "Pipeline Analysis"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    filters = models.JSONField(default=dict, help_text="Report filters configuration")
    columns = models.JSONField(
        default=list, help_text="Selected columns for the report"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_reports"
    )
    is_public = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("analytics:report_detail", kwargs={"pk": self.pk})


class SalesGoal(TimeStampedModel):
    """Sales goals and targets"""

    GOAL_TYPES = [
        ("revenue", "Revenue"),
        ("deals", "Number of Deals"),
        ("contacts", "New Contacts"),
        ("activities", "Activities"),
    ]

    PERIOD_TYPES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly"),
    ]

    name = models.CharField(max_length=200)
    goal_type = models.CharField(max_length=20, choices=GOAL_TYPES)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPES)
    target_value = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    start_date = models.DateField()
    end_date = models.DateField()
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sales_goals",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} - {self.target_value}"

    @property
    def current_progress(self):
        """Calculate current progress towards goal"""
        # This would be implemented with actual data queries
        return 0


class ActivitySummary(models.Model):
    """Daily activity summary for analytics"""

    date = models.DateField()
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="activity_summaries"
    )

    # Activity counts
    calls_made = models.PositiveIntegerField(default=0)
    emails_sent = models.PositiveIntegerField(default=0)
    meetings_held = models.PositiveIntegerField(default=0)
    tasks_completed = models.PositiveIntegerField(default=0)
    notes_added = models.PositiveIntegerField(default=0)

    # Deal metrics
    deals_created = models.PositiveIntegerField(default=0)
    deals_closed_won = models.PositiveIntegerField(default=0)
    deals_closed_lost = models.PositiveIntegerField(default=0)
    revenue_closed = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Contact metrics
    contacts_created = models.PositiveIntegerField(default=0)
    companies_created = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ["date", "user"]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user.username} - {self.date}"


class PipelineSnapshot(models.Model):
    """Pipeline snapshot for historical tracking"""

    date = models.DateField()
    stage = models.CharField(max_length=50)
    count = models.PositiveIntegerField()
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    weighted_value = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        unique_together = ["date", "stage"]
        ordering = ["-date", "stage"]

    def __str__(self):
        return f"{self.date} - {self.stage}"


class ContactEngagement(models.Model):
    """Track contact engagement metrics"""

    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="engagement_metrics"
    )
    date = models.DateField()

    # Engagement metrics
    email_opens = models.PositiveIntegerField(default=0)
    email_clicks = models.PositiveIntegerField(default=0)
    website_visits = models.PositiveIntegerField(default=0)
    social_interactions = models.PositiveIntegerField(default=0)

    # Activity metrics
    activities_count = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["contact", "date"]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.contact.full_name} - {self.date}"


class DealForecast(models.Model):
    """Deal forecasting data"""

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="forecasts")
    forecast_date = models.DateField()
    forecasted_amount = models.DecimalField(max_digits=15, decimal_places=2)
    probability = models.PositiveIntegerField()
    confidence_level = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-forecast_date"]

    def __str__(self):
        return f"{self.deal.name} - {self.forecast_date}"


class CustomField(models.Model):
    """Custom fields for contacts, companies, and deals"""

    FIELD_TYPES = [
        ("text", "Text"),
        ("number", "Number"),
        ("date", "Date"),
        ("boolean", "Boolean"),
        ("select", "Select"),
        ("multiselect", "Multi-Select"),
        ("url", "URL"),
        ("email", "Email"),
    ]

    ENTITY_TYPES = [
        ("contact", "Contact"),
        ("company", "Company"),
        ("deal", "Deal"),
        ("activity", "Activity"),
    ]

    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    options = models.JSONField(
        default=list, help_text="Options for select/multiselect fields"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["entity_type", "order", "name"]

    def __str__(self):
        return f"{self.get_entity_type_display()} - {self.label}"


class CustomFieldValue(models.Model):
    """Values for custom fields"""

    custom_field = models.ForeignKey(
        CustomField, on_delete=models.CASCADE, related_name="values"
    )

    # Generic foreign key to any model
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField()

    # Store different types of values
    text_value = models.TextField(blank=True)
    number_value = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    date_value = models.DateField(null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    json_value = models.JSONField(
        default=list, help_text="For select/multiselect values"
    )

    class Meta:
        unique_together = ["custom_field", "content_type", "object_id"]

    def __str__(self):
        return f"{self.custom_field.label}: {self.get_value()}"

    def get_value(self):
        """Return the appropriate value based on field type"""
        if self.custom_field.field_type == "text":
            return self.text_value
        elif self.custom_field.field_type == "number":
            return self.number_value
        elif self.custom_field.field_type == "date":
            return self.date_value
        elif self.custom_field.field_type == "boolean":
            return self.boolean_value
        elif self.custom_field.field_type in ["select", "multiselect"]:
            return self.json_value
        elif self.custom_field.field_type == "url":
            return self.text_value
        elif self.custom_field.field_type == "email":
            return self.text_value
        return None


class Base(TimeStampedModel):
    """Airtable-style Base (workspace) for organizing tables"""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default="📊")  # Emoji or icon name
    color = models.CharField(max_length=20, default="blue")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Base"
        verbose_name_plural = "Bases"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def tables_count(self):
        return self.tables.count()


class Table(TimeStampedModel):
    """Airtable-style Table within a Base"""

    base = models.ForeignKey(Base, on_delete=models.CASCADE, related_name="tables")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default="📋")  # Emoji or icon name
    color = models.CharField(max_length=20, default="gray")
    is_active = models.BooleanField(default=True)

    # Table configuration
    default_view = models.CharField(
        max_length=20,
        choices=[
            ("grid", "Grid View"),
            ("calendar", "Calendar View"),
            ("kanban", "Kanban View"),
            ("gallery", "Gallery View"),
        ],
        default="grid",
    )

    class Meta:
        verbose_name = "Table"
        verbose_name_plural = "Tables"
        ordering = ["base", "name"]
        unique_together = ["base", "name"]

    def __str__(self):
        return f"{self.base.name} - {self.name}"

    @property
    def records_count(self):
        return self.records.count()


# Keep DashboardTemplate for backward compatibility (to be removed later)
class DashboardTemplate(TimeStampedModel):
    """Dashboard template for CSV import and custom metrics (DEPRECATED - use Base/Table instead)"""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    csv_template = models.FileField(
        upload_to="dashboard_templates/", blank=True, null=True
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False)

    # Template configuration
    period_type = models.CharField(
        max_length=20,
        choices=[
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
            ("custom", "Custom"),
        ],
        default="weekly",
    )

    class Meta:
        verbose_name = "Dashboard Template"
        verbose_name_plural = "Dashboard Templates"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class CustomMetric(TimeStampedModel):
    """Custom metric for tracking KPIs and targets"""

    template = models.ForeignKey(
        "DashboardTemplate", on_delete=models.CASCADE, related_name="metrics"
    )
    metric_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Target and actual values
    target_value = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True
    )
    actual_value = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True
    )

    # Period information
    period = models.CharField(max_length=50)  # "Week 1", "Week 2", "Month 1", etc.
    period_start_date = models.DateField(blank=True, null=True)
    period_end_date = models.DateField(blank=True, null=True)

    # Metric configuration
    metric_type = models.CharField(
        max_length=20,
        choices=[
            ("count", "Count"),
            ("sum", "Sum"),
            ("average", "Average"),
            ("percentage", "Percentage"),
            ("currency", "Currency"),
        ],
        default="count",
    )

    unit = models.CharField(
        max_length=20, blank=True
    )  # "posts", "connections", "meetings", etc.

    class Meta:
        verbose_name = "Custom Metric"
        verbose_name_plural = "Custom Metrics"
        ordering = ["template", "period", "metric_name"]
        unique_together = ["template", "metric_name", "period"]

    def __str__(self):
        return f"{self.template.name} - {self.metric_name} ({self.period})"

    @property
    def percentage_achieved(self):
        """Calculate percentage achieved"""
        if self.target_value and self.target_value > 0:
            return round((self.actual_value or 0) / self.target_value * 100, 2)
        return 0

    @property
    def is_on_track(self):
        """Check if metric is on track (>= 80% of target)"""
        return self.percentage_achieved >= 80


class MetricDataPoint(TimeStampedModel):
    """Individual data points for metrics"""

    metric = models.ForeignKey(
        "CustomMetric", on_delete=models.CASCADE, related_name="data_points"
    )
    value = models.DecimalField(max_digits=15, decimal_places=2)
    date_recorded = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Metric Data Point"
        verbose_name_plural = "Metric Data Points"
        ordering = ["-date_recorded"]

    def __str__(self):
        return f"{self.metric.metric_name}: {self.value} ({self.date_recorded.date()})"


class DashboardView(TimeStampedModel):
    """Saved dashboard view configuration"""

    template = models.ForeignKey(
        "DashboardTemplate", on_delete=models.CASCADE, related_name="views"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    # View configuration (JSON)
    configuration = models.JSONField(default=dict)

    # Display settings
    chart_type = models.CharField(
        max_length=20,
        choices=[
            ("line", "Line Chart"),
            ("bar", "Bar Chart"),
            ("pie", "Pie Chart"),
            ("area", "Area Chart"),
            ("scatter", "Scatter Plot"),
            ("table", "Table"),
        ],
        default="line",
    )

    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Dashboard View"
        verbose_name_plural = "Dashboard Views"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.template.name} - {self.name}"


# New Airtable-style models
class TableField(TimeStampedModel):
    """Field definitions for a table (like Airtable fields)"""

    table = models.ForeignKey("Table", on_delete=models.CASCADE, related_name="fields")
    name = models.CharField(max_length=100)
    field_type = models.CharField(
        max_length=20,
        choices=[
            ("single_line_text", "Single Line Text"),
            ("long_text", "Long Text"),
            ("number", "Number"),
            ("phone_number", "Phone Number"),
            ("email", "Email"),
            ("url", "URL"),
            ("date", "Date"),
            ("checkbox", "Checkbox"),
            ("select", "Select"),
            ("multi_select", "Multi Select"),
            ("rating", "Rating"),
            ("currency", "Currency"),
            ("percentage", "Percentage"),
            ("duration", "Duration"),
        ],
        default="single_line_text",
    )
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)  # Primary field for the table
    order = models.PositiveIntegerField(default=0)

    # Field options (JSON for flexible configuration)
    options = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Table Field"
        verbose_name_plural = "Table Fields"
        ordering = ["table", "order", "name"]
        unique_together = ["table", "name"]

    def __str__(self):
        return f"{self.table.name} - {self.name}"


class Record(TimeStampedModel):
    """Individual records in a table (like Airtable records)"""

    table = models.ForeignKey("Table", on_delete=models.CASCADE, related_name="records")

    # Dynamic fields will be stored as JSON
    data = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Record"
        verbose_name_plural = "Records"
        ordering = ["-created_at"]

    def __str__(self):
        # Try to get a primary field or first field for display
        primary_field = self.table.fields.filter(is_primary=True).first()
        if primary_field and primary_field.name in self.data:
            return str(self.data[primary_field.name])
        elif self.data:
            # Use first field if no primary field
            first_key = next(iter(self.data.keys()), None)
            if first_key:
                return str(self.data[first_key])
        return f"Record {self.id}"

    def get_field_value(self, field_name):
        """Get value for a specific field"""
        return self.data.get(field_name, "")

    def set_field_value(self, field_name, value):
        """Set value for a specific field"""
        self.data[field_name] = value
        self.save()
