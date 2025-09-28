from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.shortcuts import render
from django.utils import timezone

from crm.models import Activity, Company, Contact, Deal


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

    # Monthly stats for the last 6 months
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_stats = []

    for i in range(6):
        month_start = six_months_ago + timedelta(days=i * 30)
        month_end = month_start + timedelta(days=30)

        month_data = {
            "month": month_start.strftime("%b %Y"),
            "contacts": Contact.objects.filter(
                created_at__gte=month_start, created_at__lt=month_end
            ).count(),
            "deals": Deal.objects.filter(
                created_at__gte=month_start, created_at__lt=month_end
            ).count(),
            "revenue": Deal.objects.filter(
                created_at__gte=month_start,
                created_at__lt=month_end,
                stage="closed_won",
            ).aggregate(total=Sum("amount"))["total"]
            or 0,
        }
        monthly_stats.append(month_data)

    context = {
        "total_contacts": total_contacts,
        "total_companies": total_companies,
        "total_deals": total_deals,
        "total_activities": total_activities,
        "pipeline_data": list(pipeline_data),
        "recent_activities": recent_activities,
        "upcoming_activities": upcoming_activities,
        "recent_deals": recent_deals,
        "monthly_stats": monthly_stats,
    }

    return render(request, "dashboard.html", context)


@login_required
def contact_list(request):
    """Contact list view"""
    contacts = (
        Contact.objects.filter(is_active=True)
        .select_related("company")
        .order_by("last_name", "first_name")
    )
    context = {"contacts": contacts}
    return render(request, "crm/contact_list.html", context)


@login_required
def company_list(request):
    """Company list view"""
    companies = Company.objects.filter(is_active=True).order_by("name")
    context = {"companies": companies}
    return render(request, "crm/company_list.html", context)


@login_required
def deal_list(request):
    """Deal list view"""
    deals = (
        Deal.objects.filter(is_active=True)
        .select_related("contact", "company")
        .order_by("-expected_close_date")
    )
    context = {"deals": deals}
    return render(request, "crm/deal_list.html", context)


@login_required
def activity_list(request):
    """Activity list view"""
    activities = Activity.objects.select_related("contact", "company", "deal").order_by(
        "-due_date", "-created_at"
    )
    context = {"activities": activities}
    return render(request, "crm/activity_list.html", context)
