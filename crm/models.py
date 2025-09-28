from django.db import models
from django.contrib.auth.models import User
from django.core.validators import EmailValidator, URLValidator
from django.utils import timezone
from django.urls import reverse
import uuid


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
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(validators=[EmailValidator()], blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    employee_count = models.PositiveIntegerField(null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_companies')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Companies"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('crm:company_detail', kwargs={'pk': self.pk})
    
    @property
    def full_address(self):
        """Return formatted full address"""
        parts = [self.address, self.city, self.state, self.country, self.postal_code]
        return ', '.join(filter(None, parts))


class Contact(TimeStampedModel):
    """Contact/Person model"""
    SALUTATION_CHOICES = [
        ('Mr.', 'Mr.'),
        ('Mrs.', 'Mrs.'),
        ('Ms.', 'Ms.'),
        ('Dr.', 'Dr.'),
        ('Prof.', 'Prof.'),
    ]
    
    CONTACT_STATUS_CHOICES = [
        ('lead', 'Lead'),
        ('prospect', 'Prospect'),
        ('customer', 'Customer'),
        ('inactive', 'Inactive'),
    ]
    
    # Basic Information
    salutation = models.CharField(max_length=10, choices=SALUTATION_CHOICES, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(validators=[EmailValidator()], unique=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    
    # Professional Information
    job_title = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='contacts')
    
    # Address Information
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # CRM Information
    status = models.CharField(max_length=20, choices=CONTACT_STATUS_CHOICES, default='lead')
    source = models.CharField(max_length=100, blank=True)  # How they found us
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_contacts')
    is_active = models.BooleanField(default=True)
    
    # Social Media
    linkedin_url = models.URLField(blank=True)
    twitter_handle = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['last_name', 'first_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_address(self):
        """Return formatted full address"""
        parts = [self.address, self.city, self.state, self.country, self.postal_code]
        return ', '.join(filter(None, parts))
    
    def get_absolute_url(self):
        return reverse('crm:contact_detail', kwargs={'pk': self.pk})


class Deal(TimeStampedModel):
    """Deal/Opportunity model"""
    STAGE_CHOICES = [
        ('prospecting', 'Prospecting'),
        ('qualification', 'Qualification'),
        ('proposal', 'Proposal'),
        ('negotiation', 'Negotiation'),
        ('closed_won', 'Closed Won'),
        ('closed_lost', 'Closed Lost'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='prospecting')
    probability = models.PositiveIntegerField(default=0, help_text="Probability percentage (0-100)")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Relationships
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='deals')
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='deals')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_deals')
    
    # Dates
    expected_close_date = models.DateField()
    actual_close_date = models.DateField(null=True, blank=True)
    
    # Additional fields
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-expected_close_date']
    
    def __str__(self):
        return f"{self.name} - ${self.amount}"
    
    def get_absolute_url(self):
        return reverse('crm:deal_detail', kwargs={'pk': self.pk})
    
    @property
    def weighted_amount(self):
        """Calculate weighted deal amount based on probability"""
        return self.amount * (self.probability / 100)
    
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
        ('call', 'Phone Call'),
        ('email', 'Email'),
        ('meeting', 'Meeting'),
        ('task', 'Task'),
        ('note', 'Note'),
        ('demo', 'Demo'),
        ('proposal', 'Proposal'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    subject = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Relationships
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_activities')
    
    # Scheduling
    due_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Additional fields
    duration_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Duration in minutes")
    outcome = models.TextField(blank=True, help_text="Result or outcome of the activity")
    
    class Meta:
        verbose_name_plural = "Activities"
        ordering = ['-due_date', '-created_at']
    
    def __str__(self):
        return f"{self.get_activity_type_display()}: {self.subject}"
    
    def get_absolute_url(self):
        return reverse('crm:activity_detail', kwargs={'pk': self.pk})
    
    def save(self, *args, **kwargs):
        if self.status == 'completed' and not self.completed_date:
            self.completed_date = timezone.now()
        super().save(*args, **kwargs)


class Tag(TimeStampedModel):
    """Tag model for categorizing contacts, companies, and deals"""
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code")
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class ContactTag(models.Model):
    """Many-to-many relationship between Contact and Tag"""
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ['contact', 'tag']


class CompanyTag(models.Model):
    """Many-to-many relationship between Company and Tag"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ['company', 'tag']


class DealTag(models.Model):
    """Many-to-many relationship between Deal and Tag"""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ['deal', 'tag']


class Pipeline(TimeStampedModel):
    """Sales pipeline configuration"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class PipelineStage(TimeStampedModel):
    """Pipeline stages configuration"""
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField()
    probability = models.PositiveIntegerField(default=0, help_text="Default probability percentage")
    is_closed = models.BooleanField(default=False, help_text="Is this a closed stage?")
    is_won = models.BooleanField(default=False, help_text="Is this a won stage?")
    
    class Meta:
        ordering = ['pipeline', 'order']
        unique_together = ['pipeline', 'order']
    
    def __str__(self):
        return f"{self.pipeline.name} - {self.name}"