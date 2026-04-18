"""
Utilities for sending outbound emails to contacts from the CRM.
Supports Markdown-to-HTML conversion, HTML template, and per-user signature with global fallback.
"""

from typing import Optional

import markdown
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Activity, Contact, NewsletterEdition, NewsletterIssue


def get_signature_html(user) -> str:
    """Resolve signature: per-user (UserProfile.email_signature) else global EMAIL_SIGNATURE_HTML."""
    if user:
        try:
            profile = user.profile
            if profile and getattr(profile, "email_signature", None) and profile.email_signature.strip():
                return profile.email_signature.strip()
        except Exception:
            pass
    return getattr(settings, "EMAIL_SIGNATURE_HTML", "") or ""


def render_outbound_email(
    body_markdown: str,
    signature_html: str,
    contact: Optional[Contact] = None,
) -> str:
    """Convert Markdown body to HTML and render with template and signature."""
    body_html = markdown.markdown(body_markdown or "", extensions=["nl2br"])
    return render_to_string(
        "crm/email_outbound.html",
        {
            "body_html": body_html,
            "signature_html": signature_html or "",
            "contact": contact,
        },
    )


def send_outbound_email(
    contact: Contact,
    subject: str,
    body_markdown: str,
    from_user,
    schedule_at=None,
    company=None,
) -> Activity:
    """
    Send outbound email to contact or schedule for later.

    - If schedule_at is None: send immediately, create Activity with status='sent'.
    - If schedule_at is set: create Activity with status='pending', due_date=schedule_at.
      Actual send happens when run_sequences (or run_scheduled_emails) processes it.
    """
    signature_html = get_signature_html(from_user)
    html_content = render_outbound_email(body_markdown, signature_html, contact)

    activity = Activity.objects.create(
        activity_type="email",
        direction="outbound",
        subject=subject,
        description=body_markdown,
        contact=contact,
        company=company or contact.company,
        owner=from_user,
        status="pending" if schedule_at else "sent",
        due_date=schedule_at or timezone.now(),
        completed_date=None if schedule_at else timezone.now(),
        delivery_status="queued" if schedule_at else "sent",
    )

    if schedule_at:
        return activity

    # Send immediately
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
    try:
        msg = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=from_email,
            to=[contact.email],
            connection=None,
        )
        msg.content_subtype = "html"
        msg.send()
    except Exception:
        activity.delivery_status = "failed"
        activity.status = "pending"
        activity.save(update_fields=["delivery_status", "status"])
        raise

    return activity


def process_scheduled_outbound_emails(now=None):
    """
    Process pending one-off email activities whose due_date has passed.
    Send each and update status. Returns count of emails sent.
    """
    from django.utils import timezone

    now = now or timezone.now()
    pending = (
        Activity.objects.filter(
            activity_type="email",
            status="pending",
            due_date__lte=now,
            sequence_step__isnull=True,
            sequence_enrollment__isnull=True,
            contact__email__isnull=False,
            contact__can_email_outbound=True,
        )
        .exclude(contact__email="")
        .select_related("contact", "company", "owner")
    )

    sent_count = 0
    for activity in pending:
        contact = activity.contact
        owner = activity.owner
        signature_html = get_signature_html(owner)
        html_content = render_outbound_email(
            activity.description or "",
            signature_html,
            contact,
        )
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
        try:
            msg = EmailMessage(
                subject=activity.subject,
                body=html_content,
                from_email=from_email,
                to=[contact.email],
                connection=None,
            )
            msg.content_subtype = "html"
            msg.send()
            activity.status = "sent"
            activity.delivery_status = "sent"
            activity.completed_date = now
            activity.save(update_fields=["status", "delivery_status", "completed_date"])
            sent_count += 1
        except Exception:
            activity.delivery_status = "failed"
            activity.save(update_fields=["delivery_status", "status"])
            raise

    return sent_count


def render_newsletter_email(
    body_html: str,
    contact: Optional[Contact] = None,
    preheader: Optional[str] = None,
    view_in_browser_url: Optional[str] = None,
) -> str:
    """Render newsletter HTML with dedicated template and optional unsubscribe footer."""
    from django.conf import settings as django_settings
    from django.core.signing import Signer
    from urllib.parse import quote

    unsubscribe_url = ""
    if contact and getattr(contact, "pk", None) and getattr(django_settings, "SITE_URL", ""):
        signer = Signer()
        token = quote(signer.sign(str(contact.pk)), safe="")
        base = (django_settings.SITE_URL or "").rstrip("/")
        if base:
            unsubscribe_url = f"{base}/crm/unsubscribe/?token={token}"

    return render_to_string(
        "crm/newsletter_email.html",
        {
            "body_html": body_html or "",
            "contact": contact,
            "unsubscribe_url": unsubscribe_url or None,
            "preheader": preheader or "",
            "view_in_browser_url": (view_in_browser_url or "").strip() or None,
        },
    )


def send_newsletter_edition_to_contact(contact: Contact, edition: NewsletterEdition) -> bool:
    """Send one newsletter edition to a contact. Returns True if sent successfully."""
    if not contact.email or not edition.body_html.strip():
        return False
    subject = edition.subject.strip() or (edition.weekly_theme or "Newsletter")
    html_content = render_newsletter_email(
        edition.body_html,
        contact,
        preheader=(edition.subject or edition.weekly_theme or "").strip() or None,
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
    try:
        msg = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=from_email,
            to=[contact.email],
            connection=None,
        )
        msg.content_subtype = "html"
        msg.send()
        return True
    except Exception:
        return False


def send_newsletter_issue_to_contact(contact: Contact, issue: NewsletterIssue) -> bool:
    """Send one newsletter issue (rendered from sections) to a contact. Returns True if sent successfully."""
    if not contact.email:
        return False
    body_html = issue.render_body_html()
    if not body_html.strip():
        return False
    subject = (issue.subject or issue.title or "Newsletter").strip()
    preheader_text = (
        (issue.preheader or "").strip()
        or (issue.meta_description or "").strip()
        or (issue.subject or "").strip()
        or (issue.title or "").strip()
        or None
    )
    from django.conf import settings as django_settings

    blog_base = (getattr(django_settings, "KIKODO_BLOG_API_URL", "") or "").rstrip("/") or "https://www.kikodo.app"
    view_url = f"{blog_base}/blog/{issue.slug}"
    html_content = render_newsletter_email(
        body_html,
        contact,
        preheader=preheader_text,
        view_in_browser_url=view_url or None,
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
    try:
        msg = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=from_email,
            to=[contact.email],
            connection=None,
        )
        msg.content_subtype = "html"
        msg.send()
        return True
    except Exception:
        return False


def publish_newsletter_issue(issue: NewsletterIssue, now=None):
    """
    Publish a newsletter issue: send emails to subscribers and create/update the blog post on www.kikodo.app.
    Updates issue.sent_at, issue.blog_published_at, issue.status.
    Returns (emails_sent_count, blog_ok, blog_error_message).
    """
    from django.utils import timezone

    from .models import Contact

    now = now or timezone.now()
    body_html = issue.render_body_html()
    subject = (issue.subject or issue.title or "Newsletter").strip()
    subscribers = Contact.objects.filter(
        newsletter_subscribed=True,
        can_marketing_email=True,
    ).exclude(email__isnull=True).exclude(email="")

    emails_sent = 0
    for contact in subscribers:
        try:
            if send_newsletter_issue_to_contact(contact, issue):
                Activity.objects.create(
                    activity_type="email",
                    direction="outbound",
                    subject=subject,
                    description=body_html,
                    contact=contact,
                    company=contact.company,
                    owner=issue.owner,
                    status="sent",
                    delivery_status="sent",
                    completed_date=now,
                )
                emails_sent += 1
        except Exception:
            pass

    issue.sent_at = now
    issue.save(update_fields=["sent_at"])

    from .blog_api import publish_blog_post

    blog_ok, blog_error = publish_blog_post(
        title=issue.title[:500],
        slug=issue.slug,
        body=body_html,
        body_format="html",
        meta_title=(issue.meta_title or "")[:60],
        meta_description=(issue.meta_description or "")[:320],
        published=True,
    )
    # Consider the issue "published" once the publish action has been run,
    # regardless of whether the blog API succeeded. Blog publishing failure
    # should not leave the issue stuck in Draft.
    issue.status = "published"
    if blog_ok:
        issue.blog_published_at = now
        issue.save(update_fields=["blog_published_at", "status"])
    else:
        issue.save(update_fields=["status"])

    return emails_sent, blog_ok, blog_error
