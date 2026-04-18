from datetime import datetime, timedelta

from django.conf import settings as django_settings
from django.contrib.auth import authenticate
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from .models import (
    Activity,
    Company,
    CompanyTag,
    Contact,
    ContactTag,
    Deal,
    DealTag,
    Pipeline,
    PipelineStage,
    Tag,
    WelcomeEmail,
    WelcomeEnrollment,
)
from .serializers import (
    ActivitySerializer,
    CompanySerializer,
    CompanyTagSerializer,
    ContactSerializer,
    ContactTagSerializer,
    DealSerializer,
    DealTagSerializer,
    PipelineSerializer,
    PipelineStageSerializer,
    TagSerializer,
)


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def config(request):
    """Public config for extensions (e.g. SalesNav exporter). Returns BASE_URL from .env and derived api_url."""
    base = (getattr(django_settings, "BASE_URL", "") or "").rstrip("/")
    api_url = base + "/api" if base else ""
    return Response({"base_url": base or None, "api_url": api_url or None})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([])
def newsletter_subscribe(request):
    """
    Public subscription API. POST JSON: {"name": "First Last", "email": "user@example.com"}.
    Creates or updates Contact, sets newsletter_subscribed and can_marketing_email True,
    and starts the welcome series (sends first email immediately, schedules the rest).
    Returns 201 created or 200 updated with {"status": "subscribed", "contact_id": id}.
    """
    name = (request.data.get("name") or "").strip()
    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response(
            {"error": "email is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if "@" not in email:
        return Response(
            {"error": "invalid email"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    parts = name.split(None, 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""

    contact, created = Contact.objects.update_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "newsletter_subscribed": True,
            "can_marketing_email": True,
            "source": "newsletter_signup",
        },
    )

    from .utils import pick_welcome_automation_for_new_enrollment, send_welcome_email_step

    already_enrolled = WelcomeEnrollment.objects.filter(
        contact=contact, status="active"
    ).exists()
    if not already_enrolled:
        automation = pick_welcome_automation_for_new_enrollment()
        if automation:
            steps = list(
                WelcomeEmail.objects.filter(automation=automation).order_by("order")
            )
            if steps:
                first_step = steps[0]
                sent = send_welcome_email_step(contact, first_step)
                Activity.objects.create(
                    activity_type="email",
                    direction="outbound",
                    subject=first_step.subject,
                    description=first_step.body,
                    contact=contact,
                    status="sent",
                    delivery_status="sent" if sent else "failed",
                    completed_date=timezone.now(),
                )
                if len(steps) > 1:
                    WelcomeEnrollment.objects.create(
                        contact=contact,
                        automation=automation,
                        current_step_index=1,
                        next_send_at=timezone.now()
                        + timedelta(hours=steps[1].offset_hours),
                        status="active",
                    )
                else:
                    WelcomeEnrollment.objects.create(
                        contact=contact,
                        automation=automation,
                        current_step_index=1,
                        next_send_at=None,
                        status="completed",
                    )

    payload = {"status": "subscribed", "contact_id": contact.pk}
    return Response(payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([])
def obtain_token(request):
    """
    Obtain an API token. POST with JSON: {"username": "...", "password": "..."}.
    Returns {"token": "<key>"}. Use in header: Authorization: Token <key>
    """
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    if not username or not password:
        return Response(
            {"error": "username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key})


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["industry", "is_active", "owner"]
    search_fields = ["name", "email", "industry", "phone", "city", "state"]
    ordering_fields = ["name", "created_at", "annual_revenue"]
    ordering = ["name"]

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get company statistics"""
        total_companies = self.get_queryset().count()
        active_companies = self.get_queryset().filter(is_active=True).count()

        # Industry breakdown
        industry_stats = (
            self.get_queryset()
            .values("industry")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        return Response(
            {
                "total_companies": total_companies,
                "active_companies": active_companies,
                "industry_breakdown": list(industry_stats),
            }
        )


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "is_active", "owner", "company"]
    search_fields = ["first_name", "last_name", "email", "phone", "company__name"]
    ordering_fields = ["last_name", "first_name", "created_at"]
    ordering = ["last_name", "first_name"]

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get contact statistics"""
        total_contacts = self.get_queryset().count()
        active_contacts = self.get_queryset().filter(is_active=True).count()

        # Status breakdown
        status_stats = (
            self.get_queryset()
            .values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Recent contacts (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_contacts = (
            self.get_queryset().filter(created_at__gte=thirty_days_ago).count()
        )

        return Response(
            {
                "total_contacts": total_contacts,
                "active_contacts": active_contacts,
                "recent_contacts": recent_contacts,
                "status_breakdown": list(status_stats),
            }
        )


class DealViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Deal.objects.all()
    serializer_class = DealSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["stage", "priority", "is_active", "owner", "contact", "company"]
    search_fields = [
        "name",
        "contact__first_name",
        "contact__last_name",
        "company__name",
    ]
    ordering_fields = ["name", "amount", "expected_close_date", "created_at"]
    ordering = ["-expected_close_date"]

    @action(detail=False, methods=["get"])
    def pipeline(self, request):
        """Get pipeline view with deals grouped by stage"""
        pipeline_data = (
            self.get_queryset()
            .values("stage")
            .annotate(
                count=Count("id"),
                total_amount=Sum("amount"),
                weighted_amount=Sum("amount") * Avg("probability") / 100,
            )
            .order_by("stage")
        )

        return Response(list(pipeline_data))

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get deal statistics"""
        total_deals = self.get_queryset().count()
        active_deals = self.get_queryset().filter(is_active=True).count()

        # Total pipeline value
        total_pipeline = (
            self.get_queryset()
            .filter(is_active=True)
            .aggregate(
                total=Sum("amount"), weighted=Sum("amount") * Avg("probability") / 100
            )
        )

        # Stage breakdown
        stage_stats = (
            self.get_queryset()
            .values("stage")
            .annotate(count=Count("id"), total_amount=Sum("amount"))
            .order_by("stage")
        )

        # Recent deals (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_deals = (
            self.get_queryset().filter(created_at__gte=thirty_days_ago).count()
        )

        return Response(
            {
                "total_deals": total_deals,
                "active_deals": active_deals,
                "recent_deals": recent_deals,
                "total_pipeline": total_pipeline["total"] or 0,
                "weighted_pipeline": total_pipeline["weighted"] or 0,
                "stage_breakdown": list(stage_stats),
            }
        )


class ActivityViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "activity_type",
        "status",
        "owner",
        "contact",
        "company",
        "deal",
    ]
    search_fields = [
        "subject",
        "description",
        "contact__first_name",
        "contact__last_name",
    ]
    ordering_fields = ["due_date", "created_at", "subject"]
    ordering = ["-due_date", "-created_at"]

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Get upcoming activities"""
        upcoming = (
            self.get_queryset()
            .filter(due_date__gte=timezone.now(), status="pending")
            .order_by("due_date")[:20]
        )

        serializer = self.get_serializer(upcoming, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get activity statistics"""
        total_activities = self.get_queryset().count()
        completed_activities = self.get_queryset().filter(status="completed").count()
        pending_activities = self.get_queryset().filter(status="pending").count()

        # Activity type breakdown
        type_stats = (
            self.get_queryset()
            .values("activity_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Recent activities (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_activities = (
            self.get_queryset().filter(created_at__gte=thirty_days_ago).count()
        )

        return Response(
            {
                "total_activities": total_activities,
                "completed_activities": completed_activities,
                "pending_activities": pending_activities,
                "recent_activities": recent_activities,
                "type_breakdown": list(type_stats),
            }
        )


class TagViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name"]
    ordering = ["name"]


class PipelineViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Pipeline.objects.all()
    serializer_class = PipelineSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


class PipelineStageViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = PipelineStage.objects.all()
    serializer_class = PipelineStageSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["pipeline"]
    search_fields = ["name", "pipeline__name"]
    ordering_fields = ["order", "name"]
    ordering = ["pipeline", "order"]


# Tag relationship view sets
class ContactTagViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ContactTag.objects.all()
    serializer_class = ContactTagSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["contact", "tag"]
    search_fields = ["contact__first_name", "contact__last_name", "tag__name"]


class CompanyTagViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = CompanyTag.objects.all()
    serializer_class = CompanyTagSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["company", "tag"]
    search_fields = ["company__name", "tag__name"]


class DealTagViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = DealTag.objects.all()
    serializer_class = DealTagSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["deal", "tag"]
    search_fields = ["deal__name", "tag__name"]
