import csv
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Exists, OuterRef, Prefetch, Q, Sum, Value
from django.db.models.functions import Concat
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from crm.models import (
    Activity,
    ActivityThread,
    AuditLog,
    Company,
    Contact,
    Deal,
    NewsletterAnalytics,
    NewsletterConversion,
    NewsletterEdition,
    NewsletterIssue,
    NewsletterIssueSection,
    NewsletterPlan,
    NewsletterTemplate,
    NewsletterTemplateSection,
    OperatingArea,
    PainSignal,
    PainType,
    Sequence,
    SequenceEnrollment,
    SequenceStep,
    Signal,
    WelcomeAutomation,
    WelcomeEmail,
)

from .custom_fields import (
    get_custom_field_values,
    get_custom_fields_for_entity,
    get_value_display,
    save_custom_field_values,
)
from .forms import (
    ActivityForm,
    BaseNewsletterIssueSectionFormSet,
    CompanyForm,
    ContactForm,
    CSVImportForm,
    DealForm,
    EnrollContactInSequenceForm,
    NewsletterAnalyticsForm,
    NewsletterEditionForm,
    NewsletterIssueForm,
    NewsletterPlanForm,
    NewsletterTemplateForm,
    NewsletterTemplateSectionFormSet,
    NewsletterIssueSectionFormSet,
    NewsletterIssueSectionFormSetForCreate,
    OperatingAreaFormSet,
    SendEmailForm,
    SequenceEnrollContactsForm,
    SequenceForm,
    SequenceStepFormSet,
    SignalCreateForm,
    SignalForm,
    SignalPasteForm,
    WelcomeAutomationForm,
    WelcomeEmailForm,
)
from .permissions import (
    filter_queryset_by_team,
    user_can_edit_entity,
    user_can_view_entity,
    user_is_viewer_only,
)
from .utils import (
    CSVImporter,
    find_company_duplicate_groups,
    find_contact_duplicate_groups,
    merge_companies,
    merge_contacts,
)


@login_required
def dashboard(request):
    """Main dashboard view"""
    # Get basic counts
    total_contacts = Contact.objects.filter(is_active=True).count()
    total_companies = Company.objects.filter(is_active=True).count()
    total_deals = Deal.objects.filter(is_active=True).count()
    total_activities = Activity.objects.count()

    # Pipeline data
    pipeline_data = (
        Deal.objects.filter(is_active=True)
        .values("stage")
        .annotate(count=Count("id"), total_amount=Sum("amount"))
        .order_by("stage")
    )

    # Recent activities
    recent_activities = Activity.objects.select_related(
        "contact", "company", "deal"
    ).order_by("-created_at")[:10]

    # Upcoming activities
    upcoming_activities = (
        Activity.objects.filter(due_date__gte=timezone.now(), status="pending")
        .select_related("contact", "company", "deal")
        .order_by("due_date")[:5]
    )

    # Recent deals
    recent_deals = (
        Deal.objects.filter(is_active=True)
        .select_related("contact", "company")
        .order_by("-created_at")[:5]
    )

    context = {
        "total_contacts": total_contacts,
        "total_companies": total_companies,
        "total_deals": total_deals,
        "total_activities": total_activities,
        "pipeline_data": pipeline_data,
        "recent_activities": recent_activities,
        "upcoming_activities": upcoming_activities,
        "recent_deals": recent_deals,
    }
    # Use the existing top-level dashboard template
    return render(request, "dashboard.html", context)


@login_required
def contact_bulk_delete(request):
    """Soft-delete selected contacts (POST only)."""
    if request.method != "POST":
        return redirect("crm:contact_list")
    ids = request.POST.getlist("ids")
    if not ids:
        messages.warning(request, "No contacts selected.")
        return redirect("crm:contact_list")
    try:
        pk_list = [int(i) for i in ids if i]
    except (ValueError, TypeError):
        messages.error(request, "Invalid selection.")
        return redirect("crm:contact_list")
    updated = Contact.objects.filter(pk__in=pk_list, is_active=True).update(
        is_active=False
    )
    if updated:
        messages.success(request, f"{updated} contact(s) deleted.")
    else:
        messages.warning(request, "No contacts were deleted.")
    return redirect("crm:contact_list")


@login_required
def contact_list(request):
    """Contact list view with sorting and filters (country + boolean)."""
    contacts_qs = Contact.objects.filter(is_active=True).select_related("company")
    contacts_qs = filter_queryset_by_team(contacts_qs, request.user, "owner")

    # Computed flags for activity-based filters (avoid joins + distinct() churn)
    activity_exists_qs = Activity.objects.filter(contact_id=OuterRef("pk"))
    reply_exists_qs = activity_exists_qs.exclude(outcome="")
    contacts_qs = contacts_qs.annotate(
        has_activity=Exists(activity_exists_qs),
        has_reply=Exists(reply_exists_qs),
    )

    # Country filter (distinct countries for dropdown)
    countries = (
        Contact.objects.filter(is_active=True)
        .exclude(Q(country="") | Q(country__isnull=True))
        .values_list("country", flat=True)
        .distinct()
        .order_by("country")
    )
    country = (request.GET.get("country") or "").strip()
    if country:
        contacts_qs = contacts_qs.filter(country__iexact=country)

    # Industry filter (via company; distinct industries from companies with active contacts)
    industries = (
        Company.objects.filter(contacts__is_active=True)
        .exclude(Q(industry="") | Q(industry__isnull=True))
        .values_list("industry", flat=True)
        .distinct()
        .order_by("industry")
    )
    industry_list = request.GET.getlist("industry")
    if industry_list:
        contacts_qs = contacts_qs.filter(company__industry__in=industry_list)

    # Boolean filters (single dropdown)
    verified = (request.GET.get("verified") or "").strip()
    outreach = (request.GET.get("outreach") or "").strip()
    reply = (request.GET.get("reply") or "").strip()
    pain_signal = (request.GET.get("pain_signal") or "").strip()
    has_email = (request.GET.get("has_email") or "").strip()
    has_linkedin = (request.GET.get("has_linkedin") or "").strip()
    has_company = (request.GET.get("has_company") or "").strip()
    subscribed = (request.GET.get("subscribed") or "").strip()

    if verified == "yes":
        contacts_qs = contacts_qs.filter(verified=True)
    elif verified == "no":
        contacts_qs = contacts_qs.filter(verified=False)

    # Outreach = "have I contacted them?" (any related Activity)
    if outreach == "yes":
        contacts_qs = contacts_qs.filter(has_activity=True)
    elif outreach == "no":
        contacts_qs = contacts_qs.filter(has_activity=False)

    # Reply = "did they reply?" (any related Activity with non-empty Outcome / Reply)

    if pain_signal == "yes":
        contacts_qs = contacts_qs.filter(company__pain_signals__isnull=False).distinct()
    elif pain_signal == "no":
        contacts_qs = contacts_qs.exclude(
            company__isnull=False, company__pain_signals__isnull=False
        )

    if has_email == "yes":
        contacts_qs = contacts_qs.exclude(Q(email="") | Q(email__isnull=True))
    elif has_email == "no":
        contacts_qs = contacts_qs.filter(Q(email="") | Q(email__isnull=True))

    if has_linkedin == "yes":
        contacts_qs = contacts_qs.exclude(linkedin="")
    elif has_linkedin == "no":
        contacts_qs = contacts_qs.filter(linkedin="")

    if has_company == "yes":
        contacts_qs = contacts_qs.filter(company__isnull=False)
    elif has_company == "no":
        contacts_qs = contacts_qs.filter(company__isnull=True)

    if subscribed == "yes":
        contacts_qs = contacts_qs.filter(newsletter_subscribed=True)
    elif subscribed == "no":
        contacts_qs = contacts_qs.filter(newsletter_subscribed=False)

    # Text search
    search_query = (request.GET.get("q") or "").strip()
    if search_query:
        contacts_qs = contacts_qs.annotate(
            _search_full_name=Concat("first_name", Value(" "), "last_name")
        ).filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(_search_full_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(company__name__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(mobile__icontains=search_query)
            | Q(job_title__icontains=search_query)
            | Q(city__icontains=search_query)
            | Q(state__icontains=search_query)
            | Q(country__icontains=search_query)
        )

    # Sorting (all fields)
    sort_by = request.GET.get("sort", "last_name")
    order = request.GET.get("order", "asc")
    allowed_sort_fields = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "mobile",
        "job_title",
        "company",
        "outreach_status",
        "city",
        "state",
        "country",
        "postal_code",
        "last_contact",
        "linkedin",
        "source",
        "created_at",
        "updated_at",
    ]
    if sort_by not in allowed_sort_fields:
        sort_by = "last_name"

    if sort_by == "company":
        if order == "desc":
            contacts_qs = contacts_qs.order_by(
                "-company__name", "last_name", "first_name"
            )
        else:
            contacts_qs = contacts_qs.order_by(
                "company__name", "last_name", "first_name"
            )
    else:
        if order == "desc":
            contacts_qs = contacts_qs.order_by(
                f"-{sort_by}", "last_name", "first_name"
            )
        else:
            contacts_qs = contacts_qs.order_by(sort_by, "last_name", "first_name")

    filters = {
        "country": country,
        "industry": industry_list,
        "verified": verified,
        "outreach": outreach,
        "reply": reply,
        "pain_signal": pain_signal,
        "has_email": has_email,
        "has_linkedin": has_linkedin,
        "has_company": has_company,
        "subscribed": subscribed,
    }
    filter_query = urlencode({k: v for k, v in filters.items() if v}, doseq=True)

    # Pagination
    try:
        page_size = int(request.GET.get("page_size") or 20)
    except (TypeError, ValueError):
        page_size = 20
    if page_size < 20:
        page_size = 20
    if page_size > 100:
        page_size = 100
    # Snap to nearest multiple of 20
    page_size = ((page_size - 1) // 20 + 1) * 20

    paginator = Paginator(contacts_qs, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "contacts": page_obj.object_list,
        "page_obj": page_obj,
        "page_size": page_obj.paginator.per_page,
        "page_size_options": [20, 40, 60, 80, 100],
        "countries": countries,
        "industries": industries,
        "sort_by": sort_by,
        "order": order,
        "next_order": "desc" if order == "asc" else "asc",
        "filters": filters,
        "filter_query": filter_query,
        "search_query": search_query,
    }
    return render(request, "crm/contact_list.html", context)


@login_required
def contact_create(request):
    """Create a new contact."""
    if user_is_viewer_only(request.user):
        return HttpResponseForbidden("Viewers cannot create records.")
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            if not contact.owner:
                contact.owner = request.user
            contact.save()
            messages.success(request, "Contact created successfully.")
            return redirect("crm:contact_detail", pk=contact.pk)
    else:
        form = ContactForm()

    context = {"form": form}
    return render(request, "crm/contact_form.html", context)


@login_required
def contact_edit(request, pk):
    """Edit an existing contact."""
    contact = get_object_or_404(Contact, pk=pk)
    if user_is_viewer_only(request.user):
        return HttpResponseForbidden("Viewers cannot edit.")
    if not user_can_edit_entity(request.user, contact, "owner"):
        return HttpResponseForbidden("You do not have permission to edit this contact.")
    if request.method == "POST":
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            contact = form.save()
            save_custom_field_values(contact, request.POST)
            messages.success(request, "Contact updated successfully.")
            return redirect("crm:contact_detail", pk=contact.pk)
    else:
        form = ContactForm(instance=contact)

    custom_fields_list = get_custom_fields_for_entity("contact")
    custom_values = get_custom_field_values(contact)
    custom_fields_with_values = [
        (cf, custom_values.get(cf.id)) for cf in custom_fields_list
    ]
    context = {
        "form": form,
        "contact": contact,
        "custom_fields_with_values": custom_fields_with_values,
    }
    return render(request, "crm/contact_form.html", context)


@login_required
def contact_detail(request, pk):
    """Contact detail with unified activity timeline."""
    contact = get_object_or_404(
        Contact.objects.select_related("company").prefetch_related("activities"), pk=pk
    )
    if not user_can_view_entity(request.user, contact, "owner"):
        return HttpResponseForbidden("You do not have permission to view this contact.")

    activity_qs = (
        Activity.objects.filter(contact=contact)
        .select_related("company", "deal", "thread", "sequence_enrollment")
        .order_by("-created_at")
    )

    # Filtering by activity type and owner
    activity_type = request.GET.get("type")
    owner_id = request.GET.get("owner")

    if activity_type and activity_type in dict(Activity.ACTIVITY_TYPES):
        activity_qs = activity_qs.filter(activity_type=activity_type)

    if owner_id:
        activity_qs = activity_qs.filter(owner_id=owner_id)

    # Pinned activities first, then rest
    activities = list(activity_qs)
    pinned_activities = [a for a in activities if a.is_pinned]
    regular_activities = [a for a in activities if not a.is_pinned]

    # Upcoming vs recent helper slices
    now = timezone.now()
    upcoming_activities = [
        a
        for a in activities
        if a.due_date and a.due_date >= now and a.status == "pending"
    ]
    recent_activities = activities[:10]

    # Sequence enrollments overview for this contact
    enrollments = (
        SequenceEnrollment.objects.filter(contact=contact)
        .select_related("sequence", "deal")
        .order_by("-created_at")
    )

    audit_logs = (
        AuditLog.objects.filter(
            model_name=Contact._meta.label_lower, object_id=contact.pk
        )
        .select_related("user")
        .order_by("-timestamp")[:15]
    )

    custom_fields_list = get_custom_fields_for_entity("contact")
    custom_values = get_custom_field_values(contact)
    custom_fields_data = [
        (cf, get_value_display(custom_values.get(cf.id))) for cf in custom_fields_list
    ]

    context = {
        "contact": contact,
        "pinned_activities": pinned_activities,
        "activities": regular_activities,
        "recent_activities": recent_activities,
        "upcoming_activities": upcoming_activities,
        "enrollments": enrollments,
        "audit_logs": audit_logs,
        "custom_fields_data": custom_fields_data,
        "active_type_filter": activity_type or "",
        "Activity": Activity,
    }
    return render(request, "crm/contact_detail.html", context)


@login_required
def contact_send_email(request, pk):
    """Compose and send email to contact (immediate or scheduled)."""
    contact = get_object_or_404(Contact.objects.select_related("company"), pk=pk)
    if not user_can_edit_entity(request.user, contact, "owner"):
        return HttpResponseForbidden("You do not have permission to send email to this contact.")

    if not contact.email or not contact.email.strip():
        messages.error(request, "This contact has no email address.")
        return redirect("crm:contact_detail", pk=contact.pk)

    if not contact.can_email_outbound:
        messages.error(request, "This contact has opted out of outbound emails.")
        return redirect("crm:contact_detail", pk=contact.pk)

    if request.method == "POST":
        form = SendEmailForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data["subject"]
            body = form.cleaned_data["body"]
            schedule_at = form.cleaned_data.get("schedule_at")

            from .email_utils import send_outbound_email

            try:
                activity = send_outbound_email(
                    contact=contact,
                    subject=subject,
                    body_markdown=body,
                    from_user=request.user,
                    schedule_at=schedule_at,
                    company=contact.company,
                )
                if schedule_at:
                    messages.success(
                        request,
                        f"Email scheduled for {schedule_at.strftime('%Y-%m-%d %H:%M')}. "
                        "It will be sent when run_sequences runs.",
                    )
                else:
                    messages.success(request, "Email sent successfully.")
                return redirect("crm:contact_detail", pk=contact.pk)
            except Exception as e:
                messages.error(request, f"Failed to send email: {e}")
    else:
        form = SendEmailForm()

    return render(
        request,
        "crm/send_email.html",
        {"form": form, "contact": contact},
    )


@login_required
def contact_enrich(request, pk):
    """Enrich a single contact using LLM (POST only)."""
    if request.method != "POST":
        return redirect("crm:contact_detail", pk=pk)
    contact = get_object_or_404(Contact.objects.select_related("company"), pk=pk)
    if not user_can_view_entity(request.user, contact, "owner"):
        return HttpResponseForbidden("You do not have permission to enrich this contact.")
    from .enrichment import enrich_contact_from_llm

    result = enrich_contact_from_llm(contact)
    if result["error"]:
        messages.error(request, f"Enrichment failed: {result['error']}")
    elif result["updated"]:
        parts = []
        if result["job_title"]:
            parts.append(f"job title: {result['job_title']}")
        if result["company"]:
            parts.append(f"company: {result['company'].name}")
        messages.success(request, f"Enriched contact: {', '.join(parts)}")
    else:
        messages.warning(
            request,
            "No new data could be extracted. Add headline, bio, notes, email, or LinkedIn URL.",
        )
    return redirect("crm:contact_detail", pk=pk)


@login_required
def contact_bulk_enrich(request):
    """Enrich selected contacts using LLM (POST only)."""
    if request.method != "POST":
        return redirect("crm:contact_list")
    ids = request.POST.getlist("ids")
    if not ids:
        messages.warning(request, "No contacts selected.")
        return redirect("crm:contact_list")
    try:
        pk_list = [int(i) for i in ids if i]
    except (ValueError, TypeError):
        messages.error(request, "Invalid selection.")
        return redirect("crm:contact_list")
    contacts = Contact.objects.filter(pk__in=pk_list, is_active=True).select_related("company")
    contacts = list(filter_queryset_by_team(contacts, request.user, "owner"))
    from .enrichment import enrich_contact_from_llm

    updated_count = 0
    error_count = 0
    for contact in contacts:
        result = enrich_contact_from_llm(contact)
        if result["updated"]:
            updated_count += 1
        elif result["error"]:
            error_count += 1
    if updated_count:
        messages.success(request, f"Enriched {updated_count} contact(s).")
    if error_count:
        messages.warning(request, f"{error_count} contact(s) could not be enriched (no data or LLM error).")
    if not updated_count and not error_count:
        messages.warning(
            request,
            "No contacts were enriched. They may already have company/job title, or lack headline/bio/notes/email/LinkedIn.",
        )
    return redirect("crm:contact_list")


@login_required
def company_bulk_delete(request):
    """Soft-delete selected companies (POST only)."""
    if request.method != "POST":
        return redirect("crm:company_list")
    ids = request.POST.getlist("ids")
    if not ids:
        messages.warning(request, "No companies selected.")
        return redirect("crm:company_list")
    try:
        pk_list = [int(i) for i in ids if i]
    except (ValueError, TypeError):
        messages.error(request, "Invalid selection.")
        return redirect("crm:company_list")
    updated = Company.objects.filter(pk__in=pk_list, is_active=True).update(
        is_active=False
    )
    if updated:
        messages.success(request, f"{updated} company(ies) deleted.")
    else:
        messages.warning(request, "No companies were deleted.")
    return redirect("crm:company_list")


@login_required
def company_list(request):
    """
    Company list with prospecting columns (one row per company, decision maker = first contact),
    plus simple filtering on industry, facilities, pain signal, priority tier, and outreach status.
    """
    base_qs = Company.objects.filter(is_active=True)
    base_qs = filter_queryset_by_team(base_qs, request.user, "owner")

    # Distinct industries for filter (multi-select checkboxes)
    industries = list(
        base_qs.exclude(industry="")
        .values_list("industry", flat=True)
        .distinct()
        .order_by("industry")
    )

    # Read filters from query params
    industry_list = request.GET.getlist("industry")  # multiple industries
    facilities_min = (request.GET.get("facilities_min") or "").strip()
    facilities_max = (request.GET.get("facilities_max") or "").strip()
    pain_signal = (request.GET.get("pain_signal") or "").strip()
    pain_type = (request.GET.get("pain_type") or "").strip()
    priority_tier = (request.GET.get("priority_tier") or "").strip()
    outreach_status = (request.GET.get("outreach_status") or "").strip()
    # Boolean filters (single dropdown)
    verified = (request.GET.get("verified") or "").strip()
    has_contact = (request.GET.get("has_contact") or "").strip()
    has_email = (request.GET.get("has_email") or "").strip()
    has_linkedin = (request.GET.get("has_linkedin") or "").strip()

    qs = base_qs

    if industry_list:
        qs = qs.filter(industry__in=industry_list)

    if facilities_min:
        try:
            qs = qs.filter(facility_count__gte=int(facilities_min))
        except ValueError:
            pass
    if facilities_max:
        try:
            qs = qs.filter(facility_count__lte=int(facilities_max))
        except ValueError:
            pass

    if pain_signal == "yes":
        qs = qs.filter(pain_signals__isnull=False).distinct()
    elif pain_signal == "no":
        qs = qs.filter(pain_signals__isnull=True)

    if pain_type:
        qs = qs.filter(pain_signals__pain_types__code=pain_type).distinct()

    if priority_tier in {"1", "2", "3"}:
        try:
            qs = qs.filter(priority_tier=int(priority_tier))
        except ValueError:
            pass

    if outreach_status:
        qs = qs.filter(contacts__outreach_status=outreach_status).distinct()

    if verified == "yes":
        qs = qs.filter(contacts__verified=True).distinct()
    elif verified == "no":
        qs = qs.annotate(
            _verified_count=Count(
                "contacts",
                filter=Q(contacts__is_active=True) & Q(contacts__verified=True),
            )
        ).filter(_verified_count=0)

    if has_contact == "yes":
        qs = qs.filter(contacts__is_active=True).distinct()
    elif has_contact == "no":
        qs = qs.annotate(
            _contact_count=Count("contacts", filter=Q(contacts__is_active=True))
        ).filter(_contact_count=0)

    if has_email == "yes":
        qs = (
            qs.filter(contacts__email__isnull=False)
            .exclude(contacts__email="")
            .distinct()
        )
    elif has_email == "no":
        qs = qs.annotate(
            _email_count=Count(
                "contacts",
                filter=Q(contacts__is_active=True)
                & ~Q(contacts__email="")
                & ~Q(contacts__email__isnull=True),
            )
        ).filter(_email_count=0)

    if has_linkedin == "yes":
        qs = qs.exclude(contacts__linkedin="").distinct()
    elif has_linkedin == "no":
        qs = qs.annotate(
            _linkedin_count=Count(
                "contacts",
                filter=Q(contacts__is_active=True) & ~Q(contacts__linkedin=""),
            )
        ).filter(_linkedin_count=0)

    # Text search
    search_query = (request.GET.get("q") or "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(industry__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(city__icontains=search_query)
            | Q(state__icontains=search_query)
        )

    companies_qs = qs.prefetch_related(
        Prefetch(
            "operating_areas",
            queryset=OperatingArea.objects.order_by("kind", "value"),
        ),
        Prefetch(
            "pain_signals",
            queryset=PainSignal.objects.prefetch_related("pain_types").order_by(
                "-observed_at"
            ),
        ),
        Prefetch(
            "contacts",
            queryset=Contact.objects.filter(is_active=True).order_by(
                "last_name", "first_name"
            ),
        ),
    ).order_by("name")
    pain_types = list(PainType.objects.order_by("name"))

    # Pagination
    try:
        page_size = int(request.GET.get("page_size") or 20)
    except (TypeError, ValueError):
        page_size = 20
    if page_size < 20:
        page_size = 20
    if page_size > 100:
        page_size = 100
    page_size = ((page_size - 1) // 20 + 1) * 20

    paginator = Paginator(companies_qs, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "companies": page_obj.object_list,
        "page_obj": page_obj,
        "page_size": page_obj.paginator.per_page,
        "page_size_options": [20, 40, 60, 80, 100],
        "industries": industries,
        "pain_types": pain_types,
        "filters": {
            "industry": industry_list,
            "facilities_min": facilities_min,
            "facilities_max": facilities_max,
            "pain_signal": pain_signal,
            "pain_type": pain_type,
            "priority_tier": priority_tier,
            "outreach_status": outreach_status,
            "verified": verified,
            "has_contact": has_contact,
            "has_email": has_email,
            "has_linkedin": has_linkedin,
        },
        "search_query": search_query,
    }
    return render(request, "crm/company_list.html", context)


@login_required
def company_create(request):
    """Create a new company."""
    if user_is_viewer_only(request.user):
        return HttpResponseForbidden("Viewers cannot create records.")
    if request.method == "POST":
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save(commit=False)
            if not company.owner:
                company.owner = request.user
            company.save()
            formset = OperatingAreaFormSet(request.POST, instance=company)
            if formset.is_valid():
                formset.save()
                messages.success(request, "Company created successfully.")
                return redirect("crm:company_detail", pk=company.pk)
            context = {"form": form, "formset": formset, "company": company}
        else:
            formset = OperatingAreaFormSet(request.POST, instance=Company())
            context = {"form": form, "formset": formset}
        return render(request, "crm/company_form.html", context)
    form = CompanyForm()
    formset = OperatingAreaFormSet(instance=Company())
    context = {"form": form, "formset": formset}
    return render(request, "crm/company_form.html", context)


@login_required
def company_edit(request, pk):
    """Edit an existing company."""
    company = get_object_or_404(Company, pk=pk)
    if user_is_viewer_only(request.user):
        return HttpResponseForbidden("Viewers cannot edit.")
    if not user_can_edit_entity(request.user, company, "owner"):
        return HttpResponseForbidden("You do not have permission to edit this company.")
    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        formset = OperatingAreaFormSet(request.POST, instance=company)
        if form.is_valid() and formset.is_valid():
            company = form.save()
            formset.save()
            save_custom_field_values(company, request.POST)
            messages.success(request, "Company updated successfully.")
            return redirect("crm:company_detail", pk=company.pk)
    else:
        form = CompanyForm(instance=company)
        formset = OperatingAreaFormSet(instance=company)

    custom_fields_list = get_custom_fields_for_entity("company")
    custom_values = get_custom_field_values(company)
    custom_fields_with_values = [
        (cf, custom_values.get(cf.id)) for cf in custom_fields_list
    ]

    context = {
        "form": form,
        "formset": formset,
        "company": company,
        "custom_fields_with_values": custom_fields_with_values,
    }
    return render(request, "crm/company_form.html", context)


@login_required
def company_detail(request, pk):
    """Company detail with unified activity timeline."""
    company = get_object_or_404(
        Company.objects.prefetch_related("contacts", "activities"), pk=pk
    )
    if not user_can_view_entity(request.user, company, "owner"):
        return HttpResponseForbidden("You do not have permission to view this company.")

    activity_qs = (
        Activity.objects.filter(company=company)
        .select_related("contact", "deal", "thread", "sequence_enrollment")
        .order_by("-created_at")
    )

    activity_type = request.GET.get("type")
    owner_id = request.GET.get("owner")

    if activity_type and activity_type in dict(Activity.ACTIVITY_TYPES):
        activity_qs = activity_qs.filter(activity_type=activity_type)

    if owner_id:
        activity_qs = activity_qs.filter(owner_id=owner_id)

    activities = list(activity_qs)
    pinned_activities = [a for a in activities if a.is_pinned]
    regular_activities = [a for a in activities if not a.is_pinned]

    now = timezone.now()
    upcoming_activities = [
        a
        for a in activities
        if a.due_date and a.due_date >= now and a.status == "pending"
    ]
    recent_activities = activities[:10]

    audit_logs = (
        AuditLog.objects.filter(
            model_name=Company._meta.label_lower, object_id=company.pk
        )
        .select_related("user")
        .order_by("-timestamp")[:15]
    )

    custom_fields_list = get_custom_fields_for_entity("company")
    custom_values = get_custom_field_values(company)
    custom_fields_data = [
        (cf, get_value_display(custom_values.get(cf.id))) for cf in custom_fields_list
    ]

    context = {
        "company": company,
        "pinned_activities": pinned_activities,
        "activities": regular_activities,
        "recent_activities": recent_activities,
        "upcoming_activities": upcoming_activities,
        "audit_logs": audit_logs,
        "custom_fields_data": custom_fields_data,
        "active_type_filter": activity_type or "",
        "Activity": Activity,
    }
    return render(request, "crm/company_detail.html", context)


@login_required
def deal_list(request):
    """Deal list view"""
    deals_qs = (
        Deal.objects.filter(is_active=True)
        .select_related("contact", "company", "pipeline", "pipeline_stage", "owner")
        .order_by("-expected_close_date")
    )
    deals_qs = filter_queryset_by_team(deals_qs, request.user, "owner")

    search_query = (request.GET.get("q") or "").strip()
    if search_query:
        deals_qs = deals_qs.filter(
            Q(name__icontains=search_query)
            | Q(contact__first_name__icontains=search_query)
            | Q(contact__last_name__icontains=search_query)
            | Q(company__name__icontains=search_query)
        )

    # Pagination
    try:
        page_size = int(request.GET.get("page_size") or 20)
    except (TypeError, ValueError):
        page_size = 20
    if page_size < 20:
        page_size = 20
    if page_size > 100:
        page_size = 100
    page_size = ((page_size - 1) // 20 + 1) * 20

    paginator = Paginator(deals_qs, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "deals": page_obj.object_list,
        "page_obj": page_obj,
        "page_size": page_obj.paginator.per_page,
        "page_size_options": [20, 40, 60, 80, 100],
        "search_query": search_query,
    }
    return render(request, "crm/deal_list.html", context)


@login_required
def deal_detail(request, pk):
    """Deal detail view"""
    deal = get_object_or_404(
        Deal.objects.select_related(
            "contact", "company", "owner", "pipeline", "pipeline_stage"
        ),
        pk=pk,
    )
    if not user_can_view_entity(request.user, deal, "owner"):
        return HttpResponseForbidden("You do not have permission to view this deal.")
    activities = (
        Activity.objects.filter(deal=deal)
        .select_related("contact", "company", "owner")
        .order_by("-due_date", "-created_at")[:20]
    )
    audit_logs = (
        AuditLog.objects.filter(model_name=Deal._meta.label_lower, object_id=deal.pk)
        .select_related("user")
        .order_by("-timestamp")[:15]
    )

    custom_fields_list = get_custom_fields_for_entity("deal")
    custom_values = get_custom_field_values(deal)
    custom_fields_data = [
        (cf, get_value_display(custom_values.get(cf.id))) for cf in custom_fields_list
    ]

    context = {
        "deal": deal,
        "activities": activities,
        "audit_logs": audit_logs,
        "custom_fields_data": custom_fields_data,
    }
    return render(request, "crm/deal_detail.html", context)


@login_required
def deal_create(request):
    """Create a new deal."""
    if user_is_viewer_only(request.user):
        return HttpResponseForbidden("Viewers cannot create records.")
    if request.method == "POST":
        form = DealForm(request.POST)
        if form.is_valid():
            deal = form.save(commit=False)
            if not deal.owner_id:
                deal.owner = request.user
            deal.save()
            messages.success(request, f"Deal “{deal.name}” created.")
            return redirect("crm:deal_detail", pk=deal.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        from crm.models import Pipeline

        default_pipeline = Pipeline.objects.filter(is_default=True).first()
        initial = {"owner": request.user}
        if default_pipeline:
            initial["pipeline"] = default_pipeline
        form = DealForm(data=request.GET or None, initial=initial)
    context = {"form": form, "is_edit": False}
    return render(request, "crm/deal_form.html", context)


@login_required
def deal_edit(request, pk):
    """Edit an existing deal."""
    deal = get_object_or_404(Deal, pk=pk)
    if user_is_viewer_only(request.user):
        return HttpResponseForbidden("Viewers cannot edit.")
    if not user_can_edit_entity(request.user, deal, "owner"):
        return HttpResponseForbidden("You do not have permission to edit this deal.")
    if request.method == "POST":
        form = DealForm(request.POST, instance=deal)
        if form.is_valid():
            form.save()
            messages.success(request, f"Deal “{deal.name}” updated.")
            return redirect("crm:deal_detail", pk=deal.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = DealForm(instance=deal)

    custom_fields_list = get_custom_fields_for_entity("deal")
    custom_values = get_custom_field_values(deal)
    custom_fields_with_values = [
        (cf, custom_values.get(cf.id)) for cf in custom_fields_list
    ]

    context = {
        "form": form,
        "deal": deal,
        "is_edit": True,
        "custom_fields_with_values": custom_fields_with_values,
    }
    return render(request, "crm/deal_form.html", context)


@login_required
def deal_forecast(request):
    """Simple forecast view: pipeline value by stage and by owner (weighted and total)."""
    from django.db.models import F, Sum

    deals = Deal.objects.filter(is_active=True).select_related(
        "pipeline_stage", "owner"
    )
    deals = filter_queryset_by_team(deals, request.user, "owner")

    by_stage = (
        deals.values("pipeline_stage__name", "pipeline_stage__order")
        .annotate(
            total=Sum("amount"),
            weighted=Sum(F("amount") * F("probability") / 100),
        )
        .order_by("pipeline_stage__order")
    )
    by_owner = (
        deals.values("owner__username", "owner__first_name", "owner__last_name")
        .annotate(
            total=Sum("amount"),
            weighted=Sum(F("amount") * F("probability") / 100),
        )
        .order_by("-weighted")
    )
    totals = deals.aggregate(
        total=Sum("amount"),
        weighted=Sum(F("amount") * F("probability") / 100),
    )
    context = {
        "by_stage": by_stage,
        "by_owner": by_owner,
        "totals": totals,
    }
    return render(request, "crm/deal_forecast.html", context)


@login_required
def deal_kanban(request):
    """Kanban board view for deals by pipeline stage."""
    from crm.models import Pipeline, PipelineStage

    pipeline_id = request.GET.get("pipeline")
    pipeline = None
    stages = []
    if pipeline_id:
        pipeline = get_object_or_404(
            Pipeline.objects.prefetch_related("stages"), pk=pipeline_id
        )
        stages = list(pipeline.stages.all().order_by("order"))
    else:
        pipeline = Pipeline.objects.filter(is_default=True).first()
        if pipeline:
            pipeline = Pipeline.objects.prefetch_related("stages").get(pk=pipeline.pk)
            stages = list(pipeline.stages.all().order_by("order"))
    if not pipeline:
        pipelines = Pipeline.objects.filter(is_active=True).order_by("name")
        context = {"pipeline": None, "stage_columns": [], "pipelines": pipelines}
        return render(request, "crm/deal_kanban.html", context)
    stage_columns = []
    deals_qs_base = Deal.objects.filter(is_active=True).select_related(
        "contact", "company", "owner"
    )
    deals_qs_base = filter_queryset_by_team(deals_qs_base, request.user, "owner")
    for stage in stages:
        deals = list(
            deals_qs_base.filter(pipeline_stage=stage).order_by("-expected_close_date")
        )
        stage_columns.append({"stage": stage, "deals": deals})
    pipelines = Pipeline.objects.filter(is_active=True).order_by("name")
    context = {
        "pipeline": pipeline,
        "stages": stages,
        "stage_columns": stage_columns,
        "pipelines": pipelines,
    }
    return render(request, "crm/deal_kanban.html", context)


@login_required
def deal_move_stage(request):
    """Move a deal to another pipeline stage (for Kanban drag-and-drop). Expects POST: deal_id, stage_id."""
    from crm.models import PipelineStage

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)
    deal_id = request.POST.get("deal_id")
    stage_id = request.POST.get("stage_id")
    if not deal_id or not stage_id:
        return JsonResponse(
            {"ok": False, "error": "deal_id and stage_id required"}, status=400
        )
    try:
        deal = Deal.objects.get(pk=int(deal_id), is_active=True)
        stage = PipelineStage.objects.get(pk=int(stage_id))
    except (Deal.DoesNotExist, PipelineStage.DoesNotExist, ValueError, TypeError):
        return JsonResponse(
            {"ok": False, "error": "Deal or stage not found"}, status=404
        )
    if deal.pipeline_id != stage.pipeline_id:
        return JsonResponse(
            {"ok": False, "error": "Stage does not belong to deal pipeline"}, status=400
        )
    deal.pipeline_stage = stage
    deal.probability = stage.probability
    if stage.is_closed and stage.is_won:
        deal.stage = "closed_won"
    elif stage.is_closed and not stage.is_won:
        deal.stage = "closed_lost"
    deal.save(update_fields=["pipeline_stage", "probability", "stage"])
    return JsonResponse({"ok": True, "stage_name": stage.name})


@login_required
def activity_list(request):
    """Activity list view"""
    activities_qs = Activity.objects.select_related("contact", "company", "deal")

    search_query = (request.GET.get("q") or "").strip()
    if search_query:
        activities_qs = activities_qs.filter(
            Q(subject__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(contact__first_name__icontains=search_query)
            | Q(contact__last_name__icontains=search_query)
            | Q(company__name__icontains=search_query)
        )

    # Handle sorting
    sort_by = request.GET.get("sort", "due_date")
    sort_order = request.GET.get("order", "desc")

    # Valid sort fields
    valid_sort_fields = {
        "activity_type": "activity_type",
        "subject": "subject",
        "contact": "contact__last_name",
        "company": "company__name",
        "due_date": "due_date",
        "status": "status",
        "created_at": "created_at",
    }

    # Default to due_date if invalid
    if sort_by not in valid_sort_fields:
        sort_by = "due_date"

    # Build order_by string
    order_prefix = "-" if sort_order == "desc" else ""
    order_field = f"{order_prefix}{valid_sort_fields[sort_by]}"

    # Secondary sort for consistent ordering
    if sort_by != "due_date":
        activities_qs = activities_qs.order_by(order_field, "-due_date", "-created_at")
    elif sort_by != "created_at":
        activities_qs = activities_qs.order_by(order_field, "-created_at")
    else:
        activities_qs = activities_qs.order_by(order_field)

    # Toggle order for next click
    next_order = "asc" if sort_order == "desc" else "desc"

    # Pagination
    try:
        page_size = int(request.GET.get("page_size") or 20)
    except (TypeError, ValueError):
        page_size = 20
    if page_size < 20:
        page_size = 20
    if page_size > 100:
        page_size = 100
    page_size = ((page_size - 1) // 20 + 1) * 20

    paginator = Paginator(activities_qs, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "activities": page_obj.object_list,
        "page_obj": page_obj,
        "page_size": page_obj.paginator.per_page,
        "page_size_options": [20, 40, 60, 80, 100],
        "sort_by": sort_by,
        "sort_order": sort_order,
        "next_order": next_order,
        "search_query": search_query,
    }
    return render(request, "crm/activity_list.html", context)


@login_required
def activity_create(request, contact_id=None, company_id=None, thread_id=None):
    """Create/log a new activity (communication) with a lead or company."""
    initial = {}
    if thread_id:
        try:
            thread = ActivityThread.objects.select_related("contact", "company").get(
                pk=thread_id
            )
            initial["thread"] = thread
            if thread.contact:
                initial["contact"] = thread.contact
                if thread.contact.company:
                    initial["company"] = thread.contact.company
            if thread.company:
                initial["company"] = thread.company
        except ActivityThread.DoesNotExist:
            pass
    if contact_id:
        try:
            initial["contact"] = Contact.objects.get(pk=contact_id)
            # If the contact has a company, prefill it
            if initial["contact"].company:
                initial["company"] = initial["contact"].company
        except Contact.DoesNotExist:
            pass
    if company_id:
        try:
            initial["company"] = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            pass

    if request.method == "POST":
        form = ActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            if not activity.owner:
                activity.owner = request.user
            # If a contact is chosen and no company set, auto-fill company from contact
            if activity.contact and not activity.company:
                activity.company = activity.contact.company
            # Auto-create a thread if none is set but we have a contact/company
            if not activity.thread and (activity.contact or activity.company):
                activity.thread = ActivityThread.objects.create(
                    subject=activity.subject or "",
                    contact=activity.contact,
                    company=activity.company,
                    owner=request.user,
                )
            # If no due_date was supplied, treat this as "happened now"
            if not activity.due_date:
                activity.due_date = timezone.now()
            activity.save()
            messages.success(request, "Activity logged successfully.")
            return redirect("crm:activity_list")
    else:
        initial.setdefault("activity_type", "email")
        form = ActivityForm(initial=initial)

    # Provide contacts/companies to support client-side auto-fill of company when contact changes
    # Exclude soft-deleted records so dropdowns only show active contacts/companies
    contacts_qs = (
        Contact.objects.filter(is_active=True)
        .select_related("company")
        .order_by("last_name", "first_name")
    )
    companies_qs = Company.objects.filter(is_active=True).order_by("name")

    return render(
        request,
        "crm/activity_form.html",
        {
            "form": form,
            "contacts": contacts_qs,
            "companies": companies_qs,
            "page_title": "Log Activity",
        },
    )


@login_required
def activity_edit(request, pk):
    """Edit an existing activity (e.g., log replies or update status)."""
    activity = get_object_or_404(Activity, pk=pk)
    if request.method == "POST":
        form = ActivityForm(request.POST, instance=activity)
        if form.is_valid():
            act = form.save(commit=False)
            # If contact chosen and no company, backfill company from contact
            if act.contact and not act.company:
                act.company = act.contact.company
            # Auto-create a thread if none is set but we have a contact/company
            if not act.thread and (act.contact or act.company):
                act.thread = ActivityThread.objects.create(
                    subject=act.subject or "",
                    contact=act.contact,
                    company=act.company,
                    owner=request.user,
                )
            # If status set to sent and no completed_date, set it
            if act.status == "sent" and not act.completed_date:
                act.completed_date = timezone.now()
            act.save()
            messages.success(request, "Activity updated successfully.")
            return redirect("crm:activity_list")
    else:
        form = ActivityForm(instance=activity)

    # Exclude soft-deleted records so dropdowns only show active contacts/companies.
    # When editing, include the activity's current contact/company so the selection is visible.
    contact_filter = Q(is_active=True)
    if activity.contact_id:
        contact_filter |= Q(pk=activity.contact_id)
    company_filter = Q(is_active=True)
    if activity.company_id:
        company_filter |= Q(pk=activity.company_id)

    contacts_qs = (
        Contact.objects.filter(contact_filter)
        .select_related("company")
        .order_by("last_name", "first_name")
    )
    companies_qs = Company.objects.filter(company_filter).order_by("name")

    return render(
        request,
        "crm/activity_form.html",
        {
            "form": form,
            "contacts": contacts_qs,
            "companies": companies_qs,
            "page_title": "Edit Activity",
        },
    )


@login_required
def activity_delete(request, pk):
    """Delete an activity. GET shows confirm page; POST deletes and redirects to list."""
    activity = get_object_or_404(Activity, pk=pk)
    if request.method == "POST":
        subject = activity.subject or "(no subject)"
        activity.delete()
        messages.success(request, f'Activity "{subject}" deleted.')
        return redirect("crm:activity_list")
    return render(request, "crm/activity_confirm_delete.html", {"activity": activity})


@login_required
def sequence_list(request):
    """List messaging sequences."""
    sequences_qs = Sequence.objects.all().order_by("name")

    search_query = (request.GET.get("q") or "").strip()
    if search_query:
        sequences_qs = sequences_qs.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Pagination
    try:
        page_size = int(request.GET.get("page_size") or 20)
    except (TypeError, ValueError):
        page_size = 20
    if page_size < 20:
        page_size = 20
    if page_size > 100:
        page_size = 100
    page_size = ((page_size - 1) // 20 + 1) * 20

    paginator = Paginator(sequences_qs, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "crm/sequence_list.html",
        {
            "sequences": page_obj.object_list,
            "page_obj": page_obj,
            "page_size": page_obj.paginator.per_page,
            "page_size_options": [20, 40, 60, 80, 100],
            "search_query": search_query,
        },
    )


@login_required
def sequence_create(request):
    """Create a new messaging sequence with suggested steps. Supports action=suggest to fill steps via LLM."""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "suggest":
            form = SequenceForm(request.POST)
            name = request.POST.get("name", "").strip() or "Outreach sequence"
            description = (
                request.POST.get("description", "").strip() or "General outreach"
            )
            try:
                from .signals_llm import suggest_sequence_steps

                suggested_steps = suggest_sequence_steps(name, description)
            except Exception as e:
                suggested_steps = []
                messages.warning(
                    request,
                    f"AI suggestion failed ({e}). Using default steps. Ensure Ollama is running if you want AI suggestions.",
                )
            if not suggested_steps:
                suggested_steps = [
                    {"order": 1, "offset_days": 0, "activity_type": "email"},
                    {"order": 2, "offset_days": 3, "activity_type": "email"},
                    {"order": 3, "offset_days": 7, "activity_type": "meeting"},
                    {"order": 4, "offset_days": 14, "activity_type": "email"},
                ]
            else:
                messages.success(
                    request, "Steps suggested by AI. Review and edit as needed."
                )
            formset = SequenceStepFormSet(
                initial=suggested_steps, queryset=Sequence.objects.none()
            )
            return render(
                request,
                "crm/sequence_form.html",
                {"form": form, "formset": formset, "sequence": None},
            )
        form = SequenceForm(request.POST)
        formset = SequenceStepFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            sequence = form.save(commit=False)
            sequence.owner = request.user
            sequence.save()
            formset.instance = sequence
            formset.save()
            messages.success(request, "Sequence created successfully.")
            return redirect("crm:sequence_list")
    else:
        form = SequenceForm()
        suggested_steps = [
            {"order": 1, "offset_days": 0, "activity_type": "email"},
            {"order": 2, "offset_days": 3, "activity_type": "email"},
            {"order": 3, "offset_days": 7, "activity_type": "meeting"},
            {"order": 4, "offset_days": 14, "activity_type": "email"},
        ]
        formset = SequenceStepFormSet(
            initial=suggested_steps, queryset=Sequence.objects.none()
        )

    return render(
        request,
        "crm/sequence_form.html",
        {"form": form, "formset": formset, "sequence": None},
    )


@login_required
def sequence_edit(request, pk):
    """Edit an existing sequence. Supports action=suggest to (re)fill steps via LLM."""
    sequence = get_object_or_404(Sequence, pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "suggest":
            form = SequenceForm(request.POST, instance=sequence)
            name = (
                request.POST.get("name", "").strip()
                or sequence.name
                or "Outreach sequence"
            )
            description = (
                request.POST.get("description", "").strip()
                or sequence.description
                or "General outreach"
            )
            try:
                from .signals_llm import suggest_sequence_steps

                suggested_steps = suggest_sequence_steps(name, description)
            except Exception as e:
                suggested_steps = []
                messages.warning(
                    request,
                    f"AI suggestion failed ({e}). Using default steps. Ensure Ollama is running if you want AI suggestions.",
                )
            if not suggested_steps:
                suggested_steps = [
                    {"order": 1, "offset_days": 0, "activity_type": "email"},
                    {"order": 2, "offset_days": 3, "activity_type": "email"},
                    {"order": 3, "offset_days": 7, "activity_type": "meeting"},
                    {"order": 4, "offset_days": 14, "activity_type": "email"},
                ]
            else:
                messages.success(
                    request, "Steps suggested by AI. Review and edit as needed."
                )
            formset = SequenceStepFormSet(
                initial=suggested_steps, queryset=Sequence.objects.none()
            )
            formset.instance = sequence
            return render(
                request,
                "crm/sequence_form.html",
                {"form": form, "formset": formset, "sequence": sequence},
            )
        form = SequenceForm(request.POST, instance=sequence)
        formset = SequenceStepFormSet(request.POST, instance=sequence)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Sequence updated successfully.")
            return redirect("crm:sequence_detail", pk=sequence.pk)
    else:
        form = SequenceForm(instance=sequence)
        formset = SequenceStepFormSet(instance=sequence)

    return render(
        request,
        "crm/sequence_form.html",
        {"form": form, "formset": formset, "sequence": sequence},
    )


@login_required
def sequence_detail(request, pk):
    """Show a sequence with its steps and enrolled contacts; link to add contacts."""
    sequence = get_object_or_404(Sequence, pk=pk)
    enrollments = (
        SequenceEnrollment.objects.filter(sequence=sequence)
        .select_related("contact", "deal", "owner")
        .order_by("-next_run_at", "-created_at")
    )
    steps = sequence.steps.order_by("order")
    return render(
        request,
        "crm/sequence_detail.html",
        {"sequence": sequence, "enrollments": enrollments, "steps": steps},
    )


@login_required
def sequence_enroll(request, pk):
    """Add one or more contacts to a sequence (create SequenceEnrollment and initialize)."""
    from crm.utils import initialize_sequence_enrollment

    sequence = get_object_or_404(Sequence, pk=pk)
    contacts_qs = filter_queryset_by_team(
        Contact.objects.filter(is_active=True), request.user, "owner"
    )
    form = SequenceEnrollContactsForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        selected = form.cleaned_data["contacts"]
        # Exclude contacts already enrolled in this sequence
        already = set(
            SequenceEnrollment.objects.filter(
                sequence=sequence, contact__in=selected, status="active"
            ).values_list("contact_id", flat=True)
        )
        to_enroll = [c for c in selected if c.pk not in already]
        created = 0
        for contact in to_enroll:
            enrollment = SequenceEnrollment.objects.create(
                sequence=sequence,
                contact=contact,
                owner=request.user,
                status="active",
            )
            initialize_sequence_enrollment(enrollment)
            created += 1
        if created:
            msg = f"Enrolled {created} contact(s) in «{sequence.name}»."
            if already:
                msg += f" Skipped {len(already)} already enrolled."
            messages.success(request, msg)
        else:
            if already:
                messages.warning(
                    request,
                    "Selected contact(s) are already enrolled in this sequence.",
                )
            else:
                messages.info(request, "No contacts selected.")
        return redirect("crm:sequence_detail", pk=sequence.pk)
    # Limit form queryset to team-visible contacts
    form.fields["contacts"].queryset = contacts_qs.order_by("last_name", "first_name")
    return render(
        request,
        "crm/sequence_enroll.html",
        {"sequence": sequence, "form": form},
    )


@login_required
def contact_enroll_sequence(request, contact_pk):
    """Enroll a single contact in a chosen sequence."""
    from crm.utils import initialize_sequence_enrollment

    contact = get_object_or_404(Contact, pk=contact_pk)
    if not user_can_edit_entity(request.user, contact):
        return HttpResponseForbidden()
    form = EnrollContactInSequenceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        sequence = form.cleaned_data["sequence"]
        existing = SequenceEnrollment.objects.filter(
            sequence=sequence, contact=contact, status="active"
        ).exists()
        if existing:
            messages.warning(
                request,
                f"{contact.full_name} is already enrolled in «{sequence.name}».",
            )
            return redirect("crm:contact_detail", pk=contact.pk)
        enrollment = SequenceEnrollment.objects.create(
            sequence=sequence,
            contact=contact,
            owner=request.user,
            status="active",
        )
        initialize_sequence_enrollment(enrollment)
        messages.success(
            request,
            f"Enrolled {contact.full_name} in «{sequence.name}».",
        )
        return redirect("crm:contact_detail", pk=contact.pk)
    return render(
        request,
        "crm/contact_enroll_sequence.html",
        {"contact": contact, "form": form},
    )


@login_required
def contact_import_csv(request):
    """Import contacts from CSV file."""
    if request.method == "POST":
        # Set import_type for contact import
        post_data = request.POST.copy()
        post_data["import_type"] = "contacts"
        form = CSVImportForm(post_data, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            create_companies = form.cleaned_data.get("create_companies", True)
            update_existing = form.cleaned_data.get("update_existing", False)

            importer = CSVImporter(
                user=request.user,
                create_companies=create_companies,
                update_existing=update_existing,
                import_type="contacts",
            )

            result = importer.import_csv(csv_file)

            if result["success"]:
                stats = result["stats"]

                # Show detailed results
                if (
                    stats.get("contacts_created", 0) > 0
                    or stats.get("contacts_updated", 0) > 0
                ):
                    msg = (
                        f"Import completed! "
                        f"Created {stats.get('contacts_created', 0)} contacts, "
                        f"updated {stats.get('contacts_updated', 0)} contacts."
                    )
                    if stats.get("companies_created", 0) > 0:
                        msg += f" Created {stats['companies_created']} companies."
                    messages.success(request, msg)
                elif (
                    stats.get("rows_processed", 0) == 0
                    and stats.get("rows_failed", 0) == 0
                ):
                    messages.warning(
                        request,
                        "Import completed but no rows were processed. "
                        "Check if the CSV has data rows and if column names match expected fields.",
                    )
                else:
                    messages.info(
                        request,
                        f"Import completed: {stats.get('rows_processed', 0)} rows processed, "
                        f"{stats.get('rows_failed', 0)} rows failed. "
                        "No contacts were created or updated. Check errors below.",
                    )

                # Always show warnings and errors
                if result.get("warnings"):
                    for warning in result["warnings"]:
                        messages.warning(request, warning)
                elif (
                    stats.get("contacts_created", 0) == 0
                    and stats.get("contacts_updated", 0) == 0
                ):
                    # If nothing was created and no warnings, add a helpful message
                    messages.warning(
                        request,
                        "No contacts were created. This might be because: "
                        "1) CSV columns don't match expected field names, "
                        "2) All rows are missing required fields (like email), "
                        "3) All contacts already exist and 'Update Existing' is not checked.",
                    )

                if result.get("errors"):
                    for error in result["errors"][:10]:  # Show first 10 errors
                        messages.error(request, error)
                    if len(result["errors"]) > 10:
                        messages.error(
                            request,
                            f"... and {len(result['errors']) - 10} more errors. "
                            "Check the import log for details.",
                        )

                return redirect("crm:contact_list")
            else:
                messages.error(
                    request, f"Import failed: {result.get('error', 'Unknown error')}"
                )
                if result.get("errors"):
                    for error in result["errors"][:5]:
                        messages.error(request, error)
        else:
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CSVImportForm(initial={"import_type": "contacts"})

    context = {"form": form, "import_type": "contacts"}
    return render(request, "crm/contact_import.html", context)


@login_required
def contact_duplicates(request):
    """List potential duplicate contacts (by name or email)."""
    contacts = filter_queryset_by_team(
        Contact.objects.filter(is_active=True), request.user, "owner"
    )
    groups = find_contact_duplicate_groups(contacts)
    context = {"groups": groups}
    return render(request, "crm/contact_duplicates.html", context)


@login_required
def contact_merge(request):
    """Merge selected duplicate contacts into a canonical one. POST: canonical_id, duplicate_ids (list)."""
    if request.method != "POST":
        return redirect("crm:contact_duplicates")
    if user_is_viewer_only(request.user):
        return HttpResponseForbidden("Viewers cannot merge.")
    canonical_id = request.POST.get("canonical_id")
    duplicate_ids = request.POST.getlist("duplicate_ids")
    if not canonical_id or not duplicate_ids:
        messages.error(
            request, "Select one canonical contact and at least one duplicate to merge."
        )
        return redirect("crm:contact_duplicates")
    try:
        canonical = Contact.objects.get(pk=int(canonical_id), is_active=True)
        duplicates = [
            c
            for c in Contact.objects.filter(pk__in=duplicate_ids, is_active=True)
            if c.pk != canonical.pk
        ]
    except (ValueError, Contact.DoesNotExist):
        messages.error(request, "Invalid selection.")
        return redirect("crm:contact_duplicates")
    if not duplicates:
        messages.warning(
            request,
            "No other contacts selected to merge. Choose at least one duplicate.",
        )
        return redirect("crm:contact_duplicates")
    if not user_can_edit_entity(request.user, canonical, "owner"):
        return HttpResponseForbidden(
            "You do not have permission to edit the canonical contact."
        )
    merge_contacts(canonical, duplicates)
    messages.success(
        request, f"Merged {len(duplicates)} contact(s) into {canonical.full_name}."
    )
    return redirect("crm:contact_detail", pk=canonical.pk)


@login_required
def company_import_csv(request):
    """Import companies from CSV file."""
    if request.method == "POST":
        # Set import_type for company import
        post_data = request.POST.copy()
        post_data["import_type"] = "companies"
        form = CSVImportForm(post_data, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            update_existing = form.cleaned_data.get("update_existing", False)

            importer = CSVImporter(
                user=request.user,
                create_companies=True,  # Always create for company import
                update_existing=update_existing,
                import_type="companies",
            )

            result = importer.import_csv(csv_file)

            if result["success"]:
                stats = result["stats"]

                # Show detailed results
                if (
                    stats.get("companies_created", 0) > 0
                    or stats.get("companies_updated", 0) > 0
                ):
                    msg = (
                        f"Import completed! "
                        f"Created {stats.get('companies_created', 0)} companies, "
                        f"updated {stats.get('companies_updated', 0)} companies."
                    )
                    messages.success(request, msg)
                elif (
                    stats.get("rows_processed", 0) == 0
                    and stats.get("rows_failed", 0) == 0
                ):
                    messages.warning(
                        request,
                        "Import completed but no rows were processed. "
                        "Check if the CSV has data rows and if column names match expected fields.",
                    )
                else:
                    messages.info(
                        request,
                        f"Import completed: {stats.get('rows_processed', 0)} rows processed, "
                        f"{stats.get('rows_failed', 0)} rows failed. "
                        "No companies were created or updated. Check errors below.",
                    )

                # Always show warnings and errors
                if result.get("warnings"):
                    for warning in result["warnings"]:
                        messages.warning(request, warning)
                elif (
                    stats.get("companies_created", 0) == 0
                    and stats.get("companies_updated", 0) == 0
                ):
                    # If nothing was created and no warnings, add a helpful message
                    messages.warning(
                        request,
                        "No companies were created. This might be because: "
                        "1) CSV columns don't match expected field names, "
                        "2) All rows are missing required fields (like company name), "
                        "3) All companies already exist and 'Update Existing' is not checked.",
                    )

                if result.get("errors"):
                    for error in result["errors"][:10]:
                        messages.error(request, error)
                    if len(result["errors"]) > 10:
                        messages.error(
                            request,
                            f"... and {len(result['errors']) - 10} more errors.",
                        )

                return redirect("crm:company_list")
            else:
                messages.error(
                    request, f"Import failed: {result.get('error', 'Unknown error')}"
                )
                if result.get("errors"):
                    for error in result["errors"][:5]:
                        messages.error(request, error)
        else:
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CSVImportForm(initial={"import_type": "companies"})

    context = {"form": form, "import_type": "companies"}
    return render(request, "crm/company_import.html", context)


@login_required
def company_duplicates(request):
    """List potential duplicate companies (by name or domain)."""
    companies = filter_queryset_by_team(
        Company.objects.filter(is_active=True), request.user, "owner"
    )
    groups = find_company_duplicate_groups(companies)
    context = {"groups": groups}
    return render(request, "crm/company_duplicates.html", context)


@login_required
def company_merge(request):
    """Merge selected duplicate companies into a canonical one. POST: canonical_id, duplicate_ids (list)."""
    if request.method != "POST":
        return redirect("crm:company_duplicates")
    if user_is_viewer_only(request.user):
        return HttpResponseForbidden("Viewers cannot merge.")
    canonical_id = request.POST.get("canonical_id")
    duplicate_ids = request.POST.getlist("duplicate_ids")
    if not canonical_id or not duplicate_ids:
        messages.error(
            request, "Select one canonical company and at least one duplicate to merge."
        )
        return redirect("crm:company_duplicates")
    try:
        canonical = Company.objects.get(pk=int(canonical_id), is_active=True)
        duplicates = [
            c
            for c in Company.objects.filter(pk__in=duplicate_ids, is_active=True)
            if c.pk != canonical.pk
        ]
    except (ValueError, Company.DoesNotExist):
        messages.error(request, "Invalid selection.")
        return redirect("crm:company_duplicates")
    if not duplicates:
        messages.warning(
            request,
            "No other companies selected to merge. Choose at least one duplicate.",
        )
        return redirect("crm:company_duplicates")
    if not user_can_edit_entity(request.user, canonical, "owner"):
        return HttpResponseForbidden(
            "You do not have permission to edit the canonical company."
        )
    merge_companies(canonical, duplicates)
    messages.success(
        request, f"Merged {len(duplicates)} company(ies) into {canonical.name}."
    )
    return redirect("crm:company_detail", pk=canonical.pk)


@login_required
def import_csv(request):
    """Unified CSV import view that handles both contacts and companies."""
    if request.method == "POST":
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            import_type = form.cleaned_data.get("import_type", "both")
            create_companies = form.cleaned_data.get("create_companies", True)
            update_existing = form.cleaned_data.get("update_existing", False)

            # Adjust settings based on import type
            if import_type == "contacts":
                create_companies = create_companies  # Use form value
            elif import_type == "companies":
                create_companies = True  # Always create for company-only import

            importer = CSVImporter(
                user=request.user,
                create_companies=create_companies,
                update_existing=update_existing,
                import_type=import_type,
            )

            result = importer.import_csv(csv_file)

            if result["success"]:
                stats = result["stats"]
                msg_parts = []

                if import_type in ["contacts", "both"]:
                    if stats.get("contacts_created", 0) > 0:
                        msg_parts.append(
                            f"Created {stats['contacts_created']} contacts"
                        )
                    if stats.get("contacts_updated", 0) > 0:
                        msg_parts.append(
                            f"Updated {stats['contacts_updated']} contacts"
                        )

                if import_type in ["companies", "both"]:
                    if stats.get("companies_created", 0) > 0:
                        msg_parts.append(
                            f"Created {stats['companies_created']} companies"
                        )
                    if stats.get("companies_updated", 0) > 0:
                        msg_parts.append(
                            f"Updated {stats['companies_updated']} companies"
                        )

                if msg_parts:
                    messages.success(
                        request,
                        "Import completed successfully! " + ", ".join(msg_parts) + ".",
                    )
                else:
                    messages.info(
                        request,
                        "Import completed but no records were created or updated.",
                    )

                if result.get("warnings"):
                    for warning in result["warnings"]:
                        messages.warning(request, warning)

                if result.get("errors"):
                    for error in result["errors"][:10]:
                        messages.error(request, error)
                    if len(result["errors"]) > 10:
                        messages.error(
                            request,
                            f"... and {len(result['errors']) - 10} more errors.",
                        )

                # Redirect based on import type
                if import_type == "contacts":
                    return redirect("crm:contact_list")
                elif import_type == "companies":
                    return redirect("crm:company_list")
                else:
                    return redirect("crm:dashboard")
            else:
                messages.error(
                    request, f"Import failed: {result.get('error', 'Unknown error')}"
                )
                if result.get("errors"):
                    for error in result["errors"][:5]:
                        messages.error(request, error)
    else:
        form = CSVImportForm()

    context = {"form": form, "import_type": "both"}
    return render(request, "crm/import_csv.html", context)


@login_required
def contact_export_csv(request):
    """Export contacts to CSV (contact-centric columns). Respects same filters as list view."""
    contacts = Contact.objects.filter(is_active=True).select_related("company")

    # Computed flags for activity-based filters (keep in sync with contact_list)
    activity_exists_qs = Activity.objects.filter(contact_id=OuterRef("pk"))
    reply_exists_qs = activity_exists_qs.exclude(outcome="")
    contacts = contacts.annotate(
        has_activity=Exists(activity_exists_qs),
        has_reply=Exists(reply_exists_qs),
    )

    # Apply same filters as list view
    country = (request.GET.get("country") or "").strip()
    if country:
        contacts = contacts.filter(country__iexact=country)
    industry_list = request.GET.getlist("industry")
    if industry_list:
        contacts = contacts.filter(company__industry__in=industry_list)
    verified = (request.GET.get("verified") or "").strip()
    outreach = (request.GET.get("outreach") or "").strip()
    reply = (request.GET.get("reply") or "").strip()
    pain_signal = (request.GET.get("pain_signal") or "").strip()
    has_email = (request.GET.get("has_email") or "").strip()
    has_linkedin = (request.GET.get("has_linkedin") or "").strip()
    has_company = (request.GET.get("has_company") or "").strip()
    subscribed = (request.GET.get("subscribed") or "").strip()
    if verified == "yes":
        contacts = contacts.filter(verified=True)
    elif verified == "no":
        contacts = contacts.filter(verified=False)
    if outreach == "yes":
        contacts = contacts.filter(has_activity=True)
    elif outreach == "no":
        contacts = contacts.filter(has_activity=False)

    if reply == "yes":
        contacts = contacts.filter(has_reply=True)
    elif reply == "no":
        contacts = contacts.filter(has_reply=False)
    if pain_signal == "yes":
        contacts = contacts.filter(company__pain_signals__isnull=False).distinct()
    elif pain_signal == "no":
        contacts = contacts.exclude(
            company__isnull=False, company__pain_signals__isnull=False
        )
    if has_email == "yes":
        contacts = contacts.exclude(Q(email="") | Q(email__isnull=True))
    elif has_email == "no":
        contacts = contacts.filter(Q(email="") | Q(email__isnull=True))
    if has_linkedin == "yes":
        contacts = contacts.exclude(linkedin="")
    elif has_linkedin == "no":
        contacts = contacts.filter(linkedin="")
    if has_company == "yes":
        contacts = contacts.filter(company__isnull=False)
    elif has_company == "no":
        contacts = contacts.filter(company__isnull=True)
    if subscribed == "yes":
        contacts = contacts.filter(newsletter_subscribed=True)
    elif subscribed == "no":
        contacts = contacts.filter(newsletter_subscribed=False)

    # Apply same sorting as list view
    sort_by = request.GET.get("sort", "last_name")
    order = request.GET.get("order", "asc")

    allowed_sort_fields = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "mobile",
        "job_title",
        "company",
        "status",
        "outreach_status",
        "city",
        "state",
        "country",
        "created_at",
        "updated_at",
    ]

    if sort_by not in allowed_sort_fields:
        sort_by = "last_name"

    if sort_by == "company":
        if order == "desc":
            contacts = contacts.order_by("-company__name", "last_name", "first_name")
        else:
            contacts = contacts.order_by("company__name", "last_name", "first_name")
    else:
        if order == "desc":
            contacts = contacts.order_by(f"-{sort_by}", "last_name", "first_name")
        else:
            contacts = contacts.order_by(sort_by, "last_name", "first_name")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="contacts_export.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "First Name",
            "Last Name",
            "Email",
            "Phone",
            "Mobile",
            "Job Title",
            "Department",
            "Company",
            "Status",
            "Outreach Status",
            "Verified",
            "Source",
            "Address",
            "City",
            "State",
            "Country",
            "Postal Code",
            "LinkedIn",
            "Twitter",
            "Notes",
            "Created At",
            "Updated At",
        ]
    )

    for contact in contacts:
        writer.writerow(
            [
                contact.first_name or "",
                contact.last_name or "",
                contact.email or "",
                contact.phone or "",
                contact.mobile or "",
                contact.job_title or "",
                contact.department or "",
                contact.company.name if contact.company else "",
                contact.get_status_display() if contact.status else "",
                "Contacted" if getattr(contact, "has_activity", False) else "Not contacted",
                "Yes" if contact.verified else "No",
                contact.source or "",
                contact.address or "",
                contact.city or "",
                contact.state or "",
                contact.country or "",
                contact.postal_code or "",
                contact.linkedin or "",
                contact.twitter_handle or "",
                contact.notes or "",
                (
                    contact.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if contact.created_at
                    else ""
                ),
                (
                    contact.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                    if contact.updated_at
                    else ""
                ),
            ]
        )

    return response


@login_required
def company_export_csv(request):
    """Export companies to CSV (prospecting columns + first contact). Respects same filters as list view."""
    base_qs = Company.objects.filter(is_active=True)

    # Apply same filters as list view
    industry_list = request.GET.getlist("industry")
    facilities_min = (request.GET.get("facilities_min") or "").strip()
    facilities_max = (request.GET.get("facilities_max") or "").strip()
    pain_signal = (request.GET.get("pain_signal") or "").strip()
    pain_type = (request.GET.get("pain_type") or "").strip()
    priority_tier = (request.GET.get("priority_tier") or "").strip()
    outreach_status = (request.GET.get("outreach_status") or "").strip()
    verified = (request.GET.get("verified") or "").strip()
    has_contact = (request.GET.get("has_contact") or "").strip()
    has_email = (request.GET.get("has_email") or "").strip()
    has_linkedin = (request.GET.get("has_linkedin") or "").strip()

    qs = base_qs
    if industry_list:
        qs = qs.filter(industry__in=industry_list)
    if facilities_min:
        try:
            qs = qs.filter(facility_count__gte=int(facilities_min))
        except ValueError:
            pass
    if facilities_max:
        try:
            qs = qs.filter(facility_count__lte=int(facilities_max))
        except ValueError:
            pass
    if pain_signal == "yes":
        qs = qs.filter(pain_signals__isnull=False).distinct()
    elif pain_signal == "no":
        qs = qs.filter(pain_signals__isnull=True)
    if pain_type:
        qs = qs.filter(pain_signals__pain_types__code=pain_type).distinct()
    if priority_tier in {"1", "2", "3"}:
        try:
            qs = qs.filter(priority_tier=int(priority_tier))
        except ValueError:
            pass
    if outreach_status:
        qs = qs.filter(contacts__outreach_status=outreach_status).distinct()
    if verified == "yes":
        qs = qs.filter(contacts__verified=True).distinct()
    elif verified == "no":
        qs = qs.annotate(
            _verified_count=Count(
                "contacts",
                filter=Q(contacts__is_active=True) & Q(contacts__verified=True),
            )
        ).filter(_verified_count=0)
    if has_contact == "yes":
        qs = qs.filter(contacts__is_active=True).distinct()
    elif has_contact == "no":
        qs = qs.annotate(
            _contact_count=Count("contacts", filter=Q(contacts__is_active=True))
        ).filter(_contact_count=0)
    if has_email == "yes":
        qs = (
            qs.filter(contacts__email__isnull=False)
            .exclude(contacts__email="")
            .distinct()
        )
    elif has_email == "no":
        qs = qs.annotate(
            _email_count=Count(
                "contacts",
                filter=Q(contacts__is_active=True)
                & ~Q(contacts__email="")
                & ~Q(contacts__email__isnull=True),
            )
        ).filter(_email_count=0)
    if has_linkedin == "yes":
        qs = qs.exclude(contacts__linkedin="").distinct()
    elif has_linkedin == "no":
        qs = qs.annotate(
            _linkedin_count=Count(
                "contacts",
                filter=Q(contacts__is_active=True) & ~Q(contacts__linkedin=""),
            )
        ).filter(_linkedin_count=0)

    companies = qs.prefetch_related(
        "operating_areas",
        Prefetch(
            "contacts",
            queryset=Contact.objects.filter(is_active=True).order_by(
                "last_name", "first_name"
            ),
        ),
        Prefetch(
            "pain_signals",
            queryset=PainSignal.objects.prefetch_related("pain_types").order_by(
                "-observed_at"
            ),
        ),
    ).order_by("name")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="companies_export.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Company Name",
            "# Facilities",
            "State(s)",
            "Decision Maker Name",
            "Title",
            "LinkedIn URL",
            "Company LinkedIn",
            "Email",
            "Pain Signal",
            "Pain Type",
            "Priority Tier",
            "Source",
            "Outreach Status",
            "Industry",
            "Website",
            "Phone",
            "Address",
            "City",
            "State",
            "Country",
            "Postal Code",
            "Description",
            "Annual Revenue",
            "Employee Count",
            "Founded Year",
            "Size Category",
            "Specialties",
            "ICP Fit Score",
            "ICP Fit Tier",
            "Competitor",
            "Created At",
            "Updated At",
        ]
    )

    for company in companies:
        areas = list(company.operating_areas.all())
        states_display = ", ".join(a.value for a in areas) if areas else ""
        contacts = list(company.contacts.all())
        first_contact = contacts[0] if contacts else None
        signals = list(company.pain_signals.all())
        latest_signal = signals[0] if signals else None
        pain_signal_text = (
            (latest_signal.pain_signal or "")[:500] if latest_signal else ""
        )
        pain_type_names = (
            ", ".join(t.name for t in latest_signal.pain_types.all())
            if latest_signal and latest_signal.pain_types.exists()
            else (latest_signal.get_signal_type_display() if latest_signal else "")
        )

        writer.writerow(
            [
                company.name or "",
                (
                    str(company.facility_count)
                    if company.facility_count is not None
                    else ""
                ),
                states_display,
                first_contact.full_name if first_contact else "",
                first_contact.job_title if first_contact else "",
                first_contact.linkedin if first_contact else "",
                company.linkedin_url or "",
                first_contact.email if first_contact else "",
                pain_signal_text,
                pain_type_names,
                f"Tier {company.priority_tier}" if company.priority_tier else "",
                first_contact.source if first_contact else "",
                first_contact.get_outreach_status_display() if first_contact else "",
                company.industry or "",
                company.website or "",
                company.phone or "",
                company.address or "",
                company.city or "",
                company.state or "",
                company.country or "",
                company.postal_code or "",
                company.description or "",
                str(company.annual_revenue) if company.annual_revenue else "",
                str(company.employee_count) if company.employee_count else "",
                str(company.founded_year) if company.founded_year else "",
                company.size_category or "",
                company.specialties or "",
                str(company.icp_fit_score) if company.icp_fit_score else "",
                company.icp_fit_tier or "",
                "Yes" if company.competitor else "No",
                (
                    company.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if company.created_at
                    else ""
                ),
                (
                    company.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                    if company.updated_at
                    else ""
                ),
            ]
        )

    return response


@login_required
def activity_export_csv(request):
    """Export activities to CSV"""
    activities = Activity.objects.select_related("contact", "company", "deal")

    # Apply same sorting as list view
    sort_by = request.GET.get("sort", "due_date")
    sort_order = request.GET.get("order", "desc")

    valid_sort_fields = {
        "activity_type": "activity_type",
        "subject": "subject",
        "contact": "contact__last_name",
        "company": "company__name",
        "due_date": "due_date",
        "status": "status",
        "created_at": "created_at",
    }

    if sort_by not in valid_sort_fields:
        sort_by = "due_date"

    order_prefix = "-" if sort_order == "desc" else ""
    order_field = f"{order_prefix}{valid_sort_fields[sort_by]}"

    if sort_by != "due_date":
        activities = activities.order_by(order_field, "-due_date", "-created_at")
    elif sort_by != "created_at":
        activities = activities.order_by(order_field, "-created_at")
    else:
        activities = activities.order_by(order_field)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="activities_export.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Type",
            "Subject",
            "Description",
            "Contact",
            "Company",
            "Deal",
            "Status",
            "Due Date",
            "Completed Date",
            "Duration (Minutes)",
            "Outcome",
            "Link",
            "Created At",
            "Updated At",
        ]
    )

    for activity in activities:
        writer.writerow(
            [
                activity.get_activity_type_display() if activity.activity_type else "",
                activity.subject or "",
                activity.description or "",
                activity.contact.full_name if activity.contact else "",
                activity.company.name if activity.company else "",
                activity.deal.name if activity.deal else "",
                activity.get_status_display() if activity.status else "",
                (
                    activity.due_date.strftime("%Y-%m-%d %H:%M:%S")
                    if activity.due_date
                    else ""
                ),
                (
                    activity.completed_date.strftime("%Y-%m-%d %H:%M:%S")
                    if activity.completed_date
                    else ""
                ),
                str(activity.duration_minutes) if activity.duration_minutes else "",
                activity.outcome or "",
                activity.link or "",
                (
                    activity.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if activity.created_at
                    else ""
                ),
                (
                    activity.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                    if activity.updated_at
                    else ""
                ),
            ]
        )

    return response


# --- Signals (URL + LLM-populated spreadsheet) ---


@login_required
def signal_list(request):
    """List signals (Signals-Grid style) with optional industry filter via linked company."""
    signals_qs = Signal.objects.select_related(
        "linked_contact", "linked_company"
    ).order_by("-date_logged", "-created_at")

    # Industry filter (via linked company)
    industries = (
        Company.objects.filter(signals__isnull=False)
        .exclude(Q(industry="") | Q(industry__isnull=True))
        .values_list("industry", flat=True)
        .distinct()
        .order_by("industry")
    )
    industry_list = request.GET.getlist("industry")
    if industry_list:
        signals_qs = signals_qs.filter(linked_company__industry__in=industry_list)

    search_query = (request.GET.get("q") or "").strip()
    if search_query:
        signals_qs = signals_qs.filter(
            Q(headline__icontains=search_query)
            | Q(summary__icontains=search_query)
            | Q(source_url__icontains=search_query)
        )

    sort_by = request.GET.get("sort", "date_logged")
    order = request.GET.get("order", "desc")
    allowed = [
        "date_logged",
        "headline",
        "source_type",
        "relevance",
        "status",
        "created_at",
    ]
    if sort_by not in allowed:
        sort_by = "date_logged"
    prefix = "-" if order == "desc" else ""
    signals_qs = signals_qs.order_by(f"{prefix}{sort_by}")
    next_order = "asc" if order == "desc" else "desc"

    filters = {"industry": industry_list}
    filter_query = urlencode({k: v for k, v in filters.items() if v}, doseq=True)

    # Pagination
    try:
        page_size = int(request.GET.get("page_size") or 20)
    except (TypeError, ValueError):
        page_size = 20
    if page_size < 20:
        page_size = 20
    if page_size > 100:
        page_size = 100
    page_size = ((page_size - 1) // 20 + 1) * 20

    paginator = Paginator(signals_qs, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "signals": page_obj.object_list,
        "page_obj": page_obj,
        "page_size": page_obj.paginator.per_page,
        "page_size_options": [20, 40, 60, 80, 100],
        "industries": industries,
        "filters": filters,
        "filter_query": filter_query,
        "sort_by": sort_by,
        "sort_order": order,
        "next_order": next_order,
        "search_query": search_query,
    }
    return render(request, "crm/signal_list.html", context)


def _create_signal_from_data(data):
    """Build and save a Signal from LLM data dict."""
    signal = Signal(
        source_url=data["source_url"],
        headline=data.get("headline", ""),
        date_logged=data.get("date_logged"),
        week=data.get("week", ""),
        source_type=data.get("source_type", "other"),
        relevance=data.get("relevance", "medium"),
        summary=data.get("summary", ""),
        potential_action=data.get("potential_action", ""),
        status=data.get("status", "logged"),
        competitors=data.get("competitors", ""),
        competitors_notes=data.get("competitors_notes", ""),
    )
    signal.save()
    return signal


def _update_signal_from_data(signal, data):
    """Update an existing Signal with LLM data dict."""
    signal.source_url = data.get("source_url", signal.source_url)
    signal.headline = data.get("headline", "")
    signal.date_logged = data.get("date_logged") or signal.date_logged
    signal.week = data.get("week", "")
    signal.source_type = data.get("source_type", "other")
    signal.relevance = data.get("relevance", "medium")
    signal.summary = data.get("summary", "")
    signal.potential_action = data.get("potential_action", "")
    signal.status = data.get("status", "logged")
    signal.competitors = data.get("competitors", "")
    signal.competitors_notes = data.get("competitors_notes", "")
    signal.save()
    return signal


def _ensure_companies_from_mentioned(mentioned_companies):
    """
    Create or update Company records from LLM-mentioned companies.
    Each item: name (required), industry, website, description, is_competitor.
    Returns list of (Company, created) for companies that had a valid name.
    """
    from django.core.validators import URLValidator
    from django.core.exceptions import ValidationError

    result = []
    for item in mentioned_companies or []:
        name = (item.get("name") or "").strip()[:255]
        if not name:
            continue
        is_competitor = bool(item.get("is_competitor", False))
        industry = (item.get("industry") or "").strip()[:100]
        website = (item.get("website") or "").strip()[:500]
        description = (item.get("description") or "").strip()[:2000]
        if website:
            try:
                URLValidator()(website)
            except ValidationError:
                website = ""
        company = Company.objects.filter(name__iexact=name).first()
        created = False
        if not company:
            company = Company(name=name)
            created = True
        elif company.name != name:
            company.name = name
        company.competitor = is_competitor
        if industry:
            company.industry = industry
        if website:
            company.website = website
        if description:
            company.description = description
        company.save()
        result.append((company, created))
    return result


@login_required
def signal_create_paste(request):
    """Show the paste page content form (entry point from Add Signal page). Form POSTs to signal_create."""
    if request.method != "GET":
        return redirect("crm:signal_create")
    source_url = request.GET.get("url", "").strip()
    paste_form = SignalPasteForm(initial={"source_url": source_url, "pasted_content": ""})
    return render(
        request,
        "crm/signal_paste_content.html",
        {
            "form": paste_form,
            "source_url": source_url or None,
        },
    )


@login_required
def signal_create(request):
    """Create signal: form with URL only; POST fetches URL and calls LLM to populate, then redirects to edit.
    If fetch or LLM fails (403, timeout, etc.), show paste-content form so user can add text directly."""
    if request.method == "POST":
        # Handle "paste content" step (after 403 or user chose to paste)
        pasted_content = request.POST.get("pasted_content", "").strip()
        if pasted_content:
            paste_form = SignalPasteForm(request.POST)
            if paste_form.is_valid():
                source_url = paste_form.cleaned_data.get("source_url") or ""
                try:
                    from .signals_llm import populate_signal_from_text

                    data = populate_signal_from_text(source_url, pasted_content)
                    signal = _create_signal_from_data(data)
                    companies_created = _ensure_companies_from_mentioned(
                        data.get("mentioned_companies")
                    )
                    if companies_created and not signal.linked_company:
                        signal.linked_company = companies_created[0][0]
                        signal.save()
                    if companies_created:
                        new_count = sum(1 for _, c in companies_created if c)
                        msg = "Signal created from pasted content and LLM."
                        if new_count:
                            msg += f" Added {new_count} new company(ies) to the database."
                        msg += " You can edit it below."
                        messages.success(request, msg)
                    else:
                        messages.success(
                            request,
                            "Signal created from pasted content and LLM. You can edit it below.",
                        )
                    return redirect("crm:signal_edit", pk=signal.pk)
                except Exception as e:
                    messages.error(
                        request,
                        f"LLM failed: {e}. Creating signal with URL only; you can edit and paste into Summary.",
                    )
                    signal = Signal(source_url=source_url)
                    signal.save()
                    return redirect("crm:signal_edit", pk=signal.pk)
            return render(
                request,
                "crm/signal_paste_content.html",
                {
                    "form": paste_form,
                    "source_url": paste_form.cleaned_data.get("source_url")
                    or request.POST.get("source_url", ""),
                },
            )

        # Initial step: fetch from URL
        form = SignalCreateForm(request.POST)
        if form.is_valid():
            source_url = form.cleaned_data["source_url"]
            try:
                from .signals_llm import populate_signal_from_url

                data = populate_signal_from_url(source_url)
                signal = _create_signal_from_data(data)
                companies_created = _ensure_companies_from_mentioned(
                    data.get("mentioned_companies")
                )
                if companies_created and not signal.linked_company:
                    signal.linked_company = companies_created[0][0]
                    signal.save()
                if companies_created:
                    new_count = sum(1 for _, c in companies_created if c)
                    msg = "Signal created from URL and LLM."
                    if new_count:
                        msg += f" Added {new_count} new company(ies) to the database."
                    msg += " You can edit it below."
                    messages.success(request, msg)
                else:
                    messages.success(
                        request, "Signal created from URL and LLM. You can edit it below."
                    )
                return redirect("crm:signal_edit", pk=signal.pk)
            except Exception as e:
                # For any fetch/LLM failure (403, timeout, connection error, etc.),
                # offer the paste form so the user can add text directly for LLM processing.
                try:
                    import requests.exceptions

                    is_403 = (
                        isinstance(e, requests.exceptions.HTTPError)
                        and e.response is not None
                        and e.response.status_code == 403
                    )
                except Exception:
                    is_403 = False
                paste_form = SignalPasteForm(
                    initial={"source_url": source_url, "pasted_content": ""}
                )
                return render(
                    request,
                    "crm/signal_paste_content.html",
                    {
                        "form": paste_form,
                        "source_url": source_url,
                        "error_message": str(e),
                        "is_403": is_403,
                    },
                )
    else:
        form = SignalCreateForm()
    return render(request, "crm/signal_form.html", {"form": form, "is_create": True})


@login_required
def signal_detail(request, pk):
    """Detail view for a single signal."""
    signal = get_object_or_404(
        Signal.objects.select_related("linked_contact", "linked_company"), pk=pk
    )
    return render(request, "crm/signal_detail.html", {"signal": signal})


@login_required
def signal_edit(request, pk):
    """Edit signal (all fields)."""
    signal = get_object_or_404(Signal, pk=pk)
    if request.method == "POST":
        form = SignalForm(request.POST, instance=signal)
        if form.is_valid():
            form.save()
            messages.success(request, "Signal updated.")
            return redirect("crm:signal_detail", pk=signal.pk)
    else:
        form = SignalForm(instance=signal)
    return render(
        request,
        "crm/signal_form.html",
        {"form": form, "signal": signal, "is_create": False},
    )


@login_required
def signal_populate_from_text(request, pk):
    """POST pasted_content to populate signal fields via LLM. Returns JSON for AJAX."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)
    signal = get_object_or_404(Signal, pk=pk)
    pasted_content = (request.POST.get("pasted_content") or "").strip()
    if not pasted_content:
        return JsonResponse(
            {"success": False, "error": "Please paste some content."}, status=400
        )
    source_url = signal.source_url or ""
    if not source_url:
        return JsonResponse(
            {"success": False, "error": "Signal has no source URL. Add one first."},
            status=400,
        )
    try:
        from .signals_llm import populate_signal_from_text

        data = populate_signal_from_text(source_url, pasted_content)
        _update_signal_from_data(signal, data)
        companies_created = _ensure_companies_from_mentioned(
            data.get("mentioned_companies")
        )
        if companies_created and not signal.linked_company:
            signal.linked_company = companies_created[0][0]
            signal.save()
        # Build response with field values for form population
        date_logged = data.get("date_logged")
        if hasattr(date_logged, "strftime"):
            date_logged = date_logged.strftime("%Y-%m-%d")
        return JsonResponse(
            {
                "success": True,
                "message": "Fields populated from LLM.",
                "fields": {
                    "headline": data.get("headline", ""),
                    "date_logged": date_logged or "",
                    "week": data.get("week", ""),
                    "source_type": data.get("source_type", "other"),
                    "relevance": data.get("relevance", "medium"),
                    "summary": data.get("summary", ""),
                    "potential_action": data.get("potential_action", ""),
                    "status": data.get("status", "logged"),
                    "linked_company": signal.linked_company_id or "",
                    "competitors": data.get("competitors", ""),
                    "competitors_notes": data.get("competitors_notes", ""),
                },
            }
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=500,
        )


@login_required
def signal_delete(request, pk):
    """Delete a signal. GET shows confirm page; POST deletes and redirects to list."""
    signal = get_object_or_404(Signal, pk=pk)
    if request.method == "POST":
        headline = signal.headline or signal.source_url[:50]
        signal.delete()
        messages.success(request, f"Signal “{headline}” deleted.")
        return redirect("crm:signal_list")
    return render(request, "crm/signal_confirm_delete.html", {"signal": signal})


def unsubscribe(request):
    """One-click unsubscribe from sequence/outbound emails. Expects GET ?token=<signed_contact_id>."""
    from urllib.parse import unquote

    from django.core.signing import BadSignature, Signer

    token = request.GET.get("token", "").strip()
    if not token:
        return render(
            request,
            "crm/unsubscribe.html",
            {"success": False, "error": "Missing token."},
        )
    try:
        signer = Signer()
        raw = unquote(token)
        contact_id = signer.unsign(raw)
        contact = Contact.objects.get(pk=int(contact_id))
        contact.can_email_outbound = False
        contact.newsletter_subscribed = False
        contact.save(update_fields=["can_email_outbound", "newsletter_subscribed"])
        return render(request, "crm/unsubscribe.html", {"success": True})
    except (BadSignature, ValueError, Contact.DoesNotExist):
        return render(
            request,
            "crm/unsubscribe.html",
            {"success": False, "error": "Invalid or expired link."},
        )


@login_required
def signal_export_csv(request):
    """Export signals to CSV (Signals-Grid columns). Respects same sort and industry filter as list view."""
    signals = Signal.objects.select_related("linked_contact", "linked_company")
    industry_list = request.GET.getlist("industry")
    if industry_list:
        signals = signals.filter(linked_company__industry__in=industry_list)
    sort_by = request.GET.get("sort", "date_logged")
    order = request.GET.get("order", "desc")
    allowed = [
        "date_logged",
        "headline",
        "source_type",
        "relevance",
        "status",
        "created_at",
    ]
    if sort_by not in allowed:
        sort_by = "date_logged"
    prefix = "-" if order == "desc" else ""
    signals = signals.order_by(f"{prefix}{sort_by}", "-date_logged", "-created_at")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="signals_export.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Headline / Key Point",
            "Date Logged",
            "Week",
            "Source Type",
            "Source (Link/Name)",
            "Relevance",
            "Summary",
            "Potential Action",
            "Status",
            "Linked Lead",
            "Company (from Linked Lead)",
            "Competitors",
            "Notes / Positioning",
        ]
    )
    relevance_display = {"high": "🔴 High", "medium": "🟠 Medium", "low": "⚪️ Low"}
    for s in signals:
        writer.writerow(
            [
                s.headline or "",
                s.date_logged.strftime("%Y-%m-%d") if s.date_logged else "",
                s.week or "",
                s.get_source_type_display() if s.source_type else "",
                s.source_url or "",
                relevance_display.get(s.relevance, s.relevance or ""),
                s.summary or "",
                s.potential_action or "",
                s.get_status_display() if s.status else "",
                str(s.linked_contact) if s.linked_contact else "",
                s.linked_company.name if s.linked_company else "",
                s.competitors or "",
                s.competitors_notes or "",
            ]
        )
    return response


# --- Newsletter views ---


@login_required
def newsletter_plan(request, year=None):
    """Annual newsletter plan view with quarterly tabs."""
    year = year or timezone.now().year
    plan, _ = NewsletterPlan.objects.get_or_create(
        year=year,
        defaults={"name": f"{year} Newsletter Content"},
    )
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    quarter_themes = plan.quarter_themes or {}
    active_quarter = request.GET.get("quarter", "Q1")
    if active_quarter not in quarters:
        active_quarter = "Q1"

    editions_by_quarter = {}
    for q in quarters:
        editions_by_quarter[q] = list(
            plan.editions.filter(quarter=q)
            .prefetch_related("issues")
            .order_by("week_number", "day_of_week")
        )
    editions = editions_by_quarter.get(active_quarter, [])

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_quarter_theme":
            q = request.POST.get("quarter")
            theme = request.POST.get("theme", "").strip()
            if q in quarters:
                quarter_themes[q] = theme
                plan.quarter_themes = quarter_themes
                plan.save()
                messages.success(request, f"Q{q[-1]} theme updated.")
            return redirect(f"{reverse('crm:newsletter_plan_year', kwargs={'year': year})}?quarter={q}")
        if action == "update_edition":
            edition_id = request.POST.get("edition_id")
            if edition_id:
                edition = get_object_or_404(NewsletterEdition, pk=edition_id, plan=plan)
                edition.week_number = int(request.POST.get("week_number", edition.week_number))
                edition.day_of_week = request.POST.get("day_of_week", edition.day_of_week) or "Monday"
                edition.weekly_theme = request.POST.get("weekly_theme", edition.weekly_theme)
                edition.notes = request.POST.get("notes", edition.notes)
                edition.status = request.POST.get("status", edition.status)
                edition.url = request.POST.get("url", edition.url)
                edition.save()
                messages.success(request, "Edition updated.")
            quarter = request.POST.get("quarter", active_quarter)
            return redirect(f"{reverse('crm:newsletter_plan_year', kwargs={'year': year})}?quarter={quarter}")
        if action == "add_edition":
            form = NewsletterEditionForm(request.POST)
            if form.is_valid():
                edition = form.save(commit=False)
                edition.plan = plan
                edition.quarter = active_quarter
                edition.owner = request.user
                edition.save()
                messages.success(request, "Edition added.")
            else:
                messages.error(request, "Please fix the form errors.")
            return redirect(f"{reverse('crm:newsletter_plan_year', kwargs={'year': year})}?quarter={active_quarter}")

    edition_form = NewsletterEditionForm(initial={"plan": plan, "quarter": active_quarter})
    edition_form.fields["plan"].widget = forms.HiddenInput()
    edition_form.fields["quarter"].widget = forms.HiddenInput()

    return render(
        request,
        "crm/newsletter_plan.html",
        {
            "plan": plan,
            "quarters": quarters,
            "quarter_themes": quarter_themes,
            "active_quarter": active_quarter,
            "editions": editions,
            "edition_form": edition_form,
            "day_of_week_choices": NewsletterEdition.DAY_OF_WEEK_CHOICES,
            "prev_year": plan.year - 1,
            "next_year": plan.year + 1,
        },
    )


@login_required
def welcome_automation_list(request):
    """List welcome automations (each has its own step sequence)."""
    automations = list(
        WelcomeAutomation.objects.annotate(step_count=Count("steps")).order_by("name")
    )
    return render(
        request,
        "crm/welcome_automation_list.html",
        {"automations": automations},
    )


@login_required
def welcome_automation_create(request):
    """Create a new welcome automation (empty steps; add steps from detail)."""
    if request.method == "POST":
        form = WelcomeAutomationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Welcome automation created.")
            return redirect("crm:welcome_automation_detail", pk=form.instance.pk)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = WelcomeAutomationForm()
    return render(
        request,
        "crm/welcome_automation_form.html",
        {"form": form, "automation": None},
    )


@login_required
def welcome_automation_detail(request, pk):
    """One automation: list steps and metadata."""
    automation = get_object_or_404(
        WelcomeAutomation.objects.annotate(step_count=Count("steps")),
        pk=pk,
    )
    steps = automation.steps.order_by("order")
    return render(
        request,
        "crm/welcome_automation_detail.html",
        {"automation": automation, "steps": steps},
    )


@login_required
def welcome_automation_edit(request, pk):
    """Edit automation name, active flag, and A/B weight."""
    automation = get_object_or_404(WelcomeAutomation, pk=pk)
    if request.method == "POST":
        form = WelcomeAutomationForm(request.POST, instance=automation)
        if form.is_valid():
            form.save()
            messages.success(request, "Welcome automation updated.")
            return redirect("crm:welcome_automation_detail", pk=automation.pk)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = WelcomeAutomationForm(instance=automation)
    return render(
        request,
        "crm/welcome_automation_form.html",
        {"form": form, "automation": automation},
    )


@login_required
def welcome_automation_delete(request, pk):
    """Delete an automation (only if no enrollments)."""
    automation = get_object_or_404(WelcomeAutomation, pk=pk)
    if automation.enrollments.exists():
        messages.error(
            request,
            "Cannot delete while contacts have enrollments for this automation. "
            "Deactivate it instead, or remove enrollments in Admin.",
        )
        return redirect("crm:welcome_automation_detail", pk=pk)
    if request.method == "POST":
        automation.delete()
        messages.success(request, "Welcome automation deleted.")
        return redirect("crm:welcome_automation_list")
    return render(
        request,
        "crm/welcome_automation_confirm_delete.html",
        {"automation": automation},
    )


@login_required
def welcome_step_create(request, automation_pk):
    automation = get_object_or_404(WelcomeAutomation, pk=automation_pk)
    if request.method == "POST":
        form = WelcomeEmailForm(request.POST)
        if form.is_valid():
            step = form.save(commit=False)
            step.automation = automation
            step.save()
            messages.success(request, "Step saved.")
            return redirect("crm:welcome_automation_detail", pk=automation.pk)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = WelcomeEmailForm()
    return render(
        request,
        "crm/welcome_step_form.html",
        {"form": form, "automation": automation, "step": None},
    )


@login_required
def welcome_step_edit(request, automation_pk, pk):
    automation = get_object_or_404(WelcomeAutomation, pk=automation_pk)
    step = get_object_or_404(WelcomeEmail, pk=pk, automation=automation)
    if request.method == "POST":
        form = WelcomeEmailForm(request.POST, instance=step)
        if form.is_valid():
            form.save()
            messages.success(request, "Step updated.")
            return redirect("crm:welcome_automation_detail", pk=automation.pk)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = WelcomeEmailForm(instance=step)
    return render(
        request,
        "crm/welcome_step_form.html",
        {"form": form, "automation": automation, "step": step},
    )


@login_required
def welcome_step_delete(request, automation_pk, pk):
    automation = get_object_or_404(WelcomeAutomation, pk=automation_pk)
    step = get_object_or_404(WelcomeEmail, pk=pk, automation=automation)
    if request.method == "POST":
        step.delete()
        messages.success(request, "Step deleted.")
        return redirect("crm:welcome_automation_detail", pk=automation.pk)
    return render(
        request,
        "crm/welcome_step_confirm_delete.html",
        {"automation": automation, "step": step},
    )


@login_required
def newsletter_edition_edit(request, pk):
    """Edit a single newsletter edition (full form)."""
    edition = get_object_or_404(NewsletterEdition, pk=pk)
    if request.method == "POST":
        form = NewsletterEditionForm(request.POST, instance=edition)
        if form.is_valid():
            form.save()
            messages.success(request, "Edition updated.")
            return redirect("crm:newsletter_plan_year", year=edition.plan.year)
    else:
        form = NewsletterEditionForm(instance=edition)
    return render(
        request,
        "crm/newsletter_edition_form.html",
        {"form": form, "edition": edition},
    )


@login_required
def newsletter_edition_detail(request, pk):
    """Detail view for a newsletter edition with analytics and conversions."""
    edition = get_object_or_404(
        NewsletterEdition.objects.select_related("plan"),
        pk=pk,
    )
    analytics = getattr(edition, "analytics", None)
    conversions = edition.conversions.select_related("deal", "deal__contact", "deal__company")
    return render(
        request,
        "crm/newsletter_edition_detail.html",
        {
            "edition": edition,
            "analytics": analytics,
            "conversions": conversions,
        },
    )


@login_required
def newsletter_edition_delete(request, pk):
    """Delete a newsletter edition."""
    edition = get_object_or_404(NewsletterEdition, pk=pk)
    plan_year = edition.plan.year
    if request.method == "POST":
        edition.delete()
        messages.success(request, "Edition deleted.")
        return redirect("crm:newsletter_plan_year", year=plan_year)
    return render(
        request,
        "crm/newsletter_edition_confirm_delete.html",
        {"edition": edition},
    )


@login_required
def newsletter_analytics(request):
    """Newsletter analytics dashboard: summary metrics and per-edition table."""
    year_filter = request.GET.get("year")
    selected_year = int(year_filter) if year_filter and year_filter.isdigit() else timezone.now().year
    editions = (
        NewsletterEdition.objects.select_related("plan")
        .prefetch_related("analytics", "conversions")
        .filter(plan__year=selected_year)
        .order_by("-week_number", "day_of_week")
    )

    total_subscribers = 0
    total_sent = 0
    total_opens = 0
    total_clicks = 0
    total_ad_revenue = 0
    total_conversions = 0
    editions_data = []

    for e in editions:
        try:
            a = e.analytics
        except NewsletterAnalytics.DoesNotExist:
            a = None
        if a:
            total_subscribers = max(total_subscribers, a.subscribers_count)
            total_sent += a.sent_count
            total_opens += a.opens_count
            total_clicks += a.clicks_count
            total_ad_revenue += float(a.ad_revenue or 0)
        conv_count = e.conversions.count()
        total_conversions += conv_count
        editions_data.append({
            "edition": e,
            "analytics": a,
            "conversions_count": conv_count,
        })

    plans = list(NewsletterPlan.objects.values_list("year", flat=True).distinct().order_by("-year"))

    return render(
        request,
        "crm/newsletter_analytics.html",
        {
            "editions_data": editions_data,
            "total_subscribers": total_subscribers,
            "total_sent": total_sent,
            "total_opens": total_opens,
            "total_clicks": total_clicks,
            "total_ad_revenue": total_ad_revenue,
            "total_conversions": total_conversions,
            "years": plans,
            "selected_year": selected_year,
        },
    )


# --- Newsletter templates and issues (issue creator) ---


@login_required
def newsletter_template_list(request):
    """List newsletter templates."""
    templates = NewsletterTemplate.objects.prefetch_related("sections").order_by("name")
    return render(
        request,
        "crm/newsletter_template_list.html",
        {"templates": templates},
    )


@login_required
def newsletter_template_create(request):
    """Create a new newsletter template with sections."""
    if request.method == "POST":
        form = NewsletterTemplateForm(request.POST)
        formset = NewsletterTemplateSectionFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            template = form.save()
            formset.instance = template
            formset.save()
            messages.success(request, "Template saved.")
            return redirect("crm:newsletter_template_list")
    else:
        form = NewsletterTemplateForm()
        formset = NewsletterTemplateSectionFormSet(instance=NewsletterTemplate())
    return render(
        request,
        "crm/newsletter_template_form.html",
        {"form": form, "formset": formset, "template": None},
    )


@login_required
def newsletter_template_edit(request, pk):
    """Edit a newsletter template and its sections."""
    template = get_object_or_404(NewsletterTemplate, pk=pk)
    sections_ordered = NewsletterTemplateSection.objects.filter(template=template).order_by("order")
    if request.method == "POST":
        form = NewsletterTemplateForm(request.POST, instance=template)
        formset = NewsletterTemplateSectionFormSet(
            request.POST,
            instance=template,
            queryset=sections_ordered,
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Template updated.")
            return redirect("crm:newsletter_template_list")
    else:
        form = NewsletterTemplateForm(instance=template)
        formset = NewsletterTemplateSectionFormSet(instance=template, queryset=sections_ordered)
    return render(
        request,
        "crm/newsletter_template_form.html",
        {"form": form, "formset": formset, "template": template},
    )


@login_required
def newsletter_template_delete(request, pk):
    """Delete a newsletter template."""
    template = get_object_or_404(NewsletterTemplate, pk=pk)
    if request.method == "POST":
        template.delete()
        messages.success(request, "Template deleted.")
        return redirect("crm:newsletter_template_list")
    return render(
        request,
        "crm/newsletter_template_confirm_delete.html",
        {"template": template},
    )


@login_required
def newsletter_issue_list(request):
    """List newsletter issues (drafts and published)."""
    if request.method == "POST":
        # Form must not post here; redirect to create so data is not lost
        messages.warning(
            request,
            "Use “New issue” to create drafts. Redirecting to the create form.",
        )
        return redirect("crm:newsletter_issue_create")
    issues = (
        NewsletterIssue.objects.select_related("owner", "created_from_template")
        .prefetch_related("sections")
        .order_by("-created_at")
    )
    return render(
        request,
        "crm/newsletter_issue_list.html",
        {"issues": issues},
    )


@login_required
def newsletter_issue_create(request):
    """Create a new newsletter issue. Optional ?from_template=<pk> or ?from_edition=<pk> to prepopulate from template or plan edition."""
    from_template = None
    from_edition = None
    if request.GET.get("from_template"):
        from_template = get_object_or_404(
            NewsletterTemplate.objects.prefetch_related("sections"),
            pk=request.GET.get("from_template"),
        )
    if request.GET.get("from_edition"):
        from_edition = get_object_or_404(
            NewsletterEdition.objects.select_related("plan"),
            pk=request.GET.get("from_edition"),
        )
    if request.method == "POST":
        form = NewsletterIssueForm(request.POST)
        formset = NewsletterIssueSectionFormSetForCreate(request.POST)
        if form.is_valid() and formset.is_valid():
            issue = form.save(commit=False)
            issue.owner = request.user
            edition_id = request.POST.get("from_edition")
            if edition_id:
                try:
                    issue.edition_id = int(edition_id)
                except (TypeError, ValueError):
                    pass
            # Auto-generate slug for drafts when left blank so save always succeeds
            if not (issue.slug and issue.slug.strip()):
                base = slugify(issue.title) or "newsletter"
                base = base[:500]
                slug = base
                n = 0
                while NewsletterIssue.objects.filter(slug=slug).exists():
                    n += 1
                    suffix = f"-{n}"
                    slug = (base[: 500 - len(suffix)] + suffix) if len(base) + len(suffix) > 500 else base + suffix
                issue.slug = slug
            issue.save()
            formset.instance = issue
            formset.save()
            messages.success(request, "Issue saved.")
            return redirect("crm:newsletter_issue_detail", pk=issue.pk)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        if from_edition:
            ed = from_edition
            sd = ed.scheduled_date
            title = (ed.weekly_theme or "").strip() or (f"Issue {sd}" if sd else "New issue")
            form_initial = {
                "title": title,
                "slug": "",
                "subject": ed.subject or "",
                "scheduled_date": sd,
                "status": "draft",
            }
            section_heading = (ed.weekly_theme or "").strip() or "Content"
            section_body = (ed.notes or "").strip() or (ed.body_html or "").strip()
            if section_body and section_body.startswith("<"):
                import re
                section_body = re.sub(r"<[^>]+>", " ", section_body)
                section_body = re.sub(r"\s+", " ", section_body).strip()
            initial_sections = [{"order": 0, "heading": section_heading, "body_markdown": section_body[: 2000]}]
            form = NewsletterIssueForm(initial=form_initial)
            from django.forms import inlineformset_factory
            from .models import NewsletterIssueSection
            section_formset_class = inlineformset_factory(
                NewsletterIssue,
                NewsletterIssueSection,
                fields=["order", "heading", "body_markdown"],
                extra=max(2, len(initial_sections) + 2),
                can_delete=True,
                formset=BaseNewsletterIssueSectionFormSet,
                widgets={
                    "heading": forms.TextInput(attrs={"placeholder": "Section heading", "class": "form-control"}),
                    "body_markdown": forms.Textarea(attrs={"rows": 4, "placeholder": "Markdown content", "class": "form-control"}),
                },
            )
            formset = section_formset_class(instance=NewsletterIssue(), initial=initial_sections)
        elif from_template:
            form = NewsletterIssueForm(initial={"created_from_template": from_template.pk, "title": from_template.name, "slug": ""})
            initial_sections = [
                {"order": s.order, "heading": s.heading, "body_markdown": s.body_markdown}
                for s in from_template.sections.order_by("order")
            ]
            from django.forms import inlineformset_factory
            from .models import NewsletterIssueSection
            section_formset_class = inlineformset_factory(
                NewsletterIssue,
                NewsletterIssueSection,
                fields=["order", "heading", "body_markdown"],
                extra=max(2, len(initial_sections) + 2),
                can_delete=True,
                formset=BaseNewsletterIssueSectionFormSet,
                widgets={
                    "heading": forms.TextInput(attrs={"placeholder": "Section heading", "class": "form-control"}),
                    "body_markdown": forms.Textarea(attrs={"rows": 4, "placeholder": "Markdown content", "class": "form-control"}),
                },
            )
            formset = section_formset_class(instance=NewsletterIssue(), initial=initial_sections)
        else:
            form = NewsletterIssueForm()
            formset = NewsletterIssueSectionFormSetForCreate(instance=NewsletterIssue())
    return render(
        request,
        "crm/newsletter_issue_form.html",
        {"form": form, "formset": formset, "issue": None, "from_template": from_template, "from_edition": from_edition},
    )


@login_required
def newsletter_issue_edit(request, pk):
    """Edit a newsletter issue and its sections."""
    issue = get_object_or_404(
        NewsletterIssue.objects.prefetch_related(
            Prefetch("sections", queryset=NewsletterIssueSection.objects.order_by("order"))
        ),
        pk=pk,
    )
    if issue.status == "published":
        messages.warning(request, "This issue is already published; you can still edit metadata and sections.")
    sections_ordered = NewsletterIssueSection.objects.filter(issue=issue).order_by("order")
    if request.method == "POST":
        form = NewsletterIssueForm(request.POST, instance=issue)
        formset = NewsletterIssueSectionFormSet(request.POST, instance=issue, queryset=sections_ordered)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Issue updated.")
            return redirect("crm:newsletter_issue_detail", pk=issue.pk)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = NewsletterIssueForm(instance=issue)
        formset = NewsletterIssueSectionFormSet(instance=issue, queryset=sections_ordered)
    return render(
        request,
        "crm/newsletter_issue_form.html",
        {"form": form, "formset": formset, "issue": issue},
    )


@login_required
def newsletter_issue_detail(request, pk):
    """Detail view for a newsletter issue; includes Publish button."""
    issue = get_object_or_404(
        NewsletterIssue.objects.select_related("owner", "created_from_template", "edition", "edition__plan").prefetch_related(
            Prefetch("sections", queryset=NewsletterIssueSection.objects.order_by("order"))
        ),
        pk=pk,
    )
    return render(
        request,
        "crm/newsletter_issue_detail.html",
        {"issue": issue},
    )


@login_required
def newsletter_issue_preview(request, pk):
    """Preview the newsletter issue as HTML (as it would appear in email or on the blog)."""
    issue = get_object_or_404(
        NewsletterIssue.objects.prefetch_related(
            Prefetch("sections", queryset=NewsletterIssueSection.objects.order_by("order"))
        ),
        pk=pk,
    )
    body_html = issue.render_body_html()
    return render(
        request,
        "crm/newsletter_preview.html",
        {
            "issue": issue,
            "body_html": body_html,
            "title": issue.title or issue.slug,
        },
    )


@login_required
def newsletter_issue_publish(request, pk):
    """Publish the issue: send emails to subscribers and create blog post on www.kikodo.app."""
    if request.method != "POST":
        return redirect("crm:newsletter_issue_detail", pk=pk)
    issue = get_object_or_404(NewsletterIssue, pk=pk)
    if issue.status == "published":
        messages.info(request, "This issue is already published.")
        return redirect("crm:newsletter_issue_detail", pk=pk)
    from crm.email_utils import publish_newsletter_issue
    emails_sent, blog_ok, blog_error = publish_newsletter_issue(issue)
    if blog_ok:
        messages.success(
            request,
            f"Published: {emails_sent} email(s) sent and blog post created on www.kikodo.app.",
        )
    else:
        messages.warning(
            request,
            f"Emails sent: {emails_sent}. Blog post failed: {blog_error or 'unknown'}",
        )
    return redirect("crm:newsletter_issue_detail", pk=pk)


@login_required
def newsletter_issue_test(request, pk):
    """Send the issue email to DEFAULT_FROM_EMAIL as a test (no status change)."""
    if request.method != "POST":
        return redirect("crm:newsletter_issue_detail", pk=pk)

    issue = get_object_or_404(NewsletterIssue, pk=pk)
    from django.conf import settings as django_settings
    from django.core.mail import EmailMessage

    from crm.email_utils import render_newsletter_email

    from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "").strip() or "noreply@example.com"
    recipient = from_email
    if not recipient:
        messages.error(request, "DEFAULT_FROM_EMAIL is not configured; cannot send test email.")
        return redirect("crm:newsletter_issue_detail", pk=pk)

    body_html = issue.render_body_html()
    if not body_html.strip():
        messages.warning(request, "This issue has no renderable content; add sections and try again.")
        return redirect("crm:newsletter_issue_detail", pk=pk)

    subject = (issue.subject or issue.title or "Newsletter").strip()
    preheader_text = (
        (issue.preheader or "").strip()
        or (issue.meta_description or "").strip()
        or (issue.subject or "").strip()
        or (issue.title or "").strip()
        or None
    )
    blog_base = (getattr(django_settings, "KIKODO_BLOG_API_URL", "") or "").rstrip("/") or "https://www.kikodo.app"
    view_url = f"{blog_base}/blog/{issue.slug}"
    html_content = render_newsletter_email(
        body_html,
        contact=None,
        preheader=preheader_text,
        view_in_browser_url=view_url or None,
    )

    msg = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=from_email,
        to=[recipient],
        connection=None,
    )
    msg.content_subtype = "html"
    try:
        msg.send()
        messages.success(request, f"Test email sent to {recipient}.")
    except Exception as e:
        messages.error(request, f"Test email failed: {e}")
    return redirect("crm:newsletter_issue_detail", pk=pk)


@login_required
def newsletter_issue_delete(request, pk):
    """Delete a newsletter issue."""
    issue = get_object_or_404(NewsletterIssue, pk=pk)
    if request.method == "POST":
        issue.delete()
        messages.success(request, "Issue deleted.")
        return redirect("crm:newsletter_issue_list")
    return render(
        request,
        "crm/newsletter_issue_confirm_delete.html",
        {"issue": issue},
    )
