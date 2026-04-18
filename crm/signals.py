"""
Signals for CRM notifications (e.g. task manager alerts for pending activities).
"""

import contextvars
import logging
import smtplib
import time

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Activity, NewsletterEdition

logger = logging.getLogger(__name__)

_activity_old_status = contextvars.ContextVar("activity_old_status", default=None)


def _send_pending_notification_email(activity: Activity) -> None:
    """Send email to TASK_MANAGER (blocking). Called from background thread."""
    task_manager = getattr(settings, "TASK_MANAGER", None)
    if not task_manager:
        logger.warning(
            "TASK_MANAGER not configured; skipping pending activity notification for Activity %s",
            activity.pk,
        )
        return

    type_label = dict(Activity.ACTIVITY_TYPES).get(activity.activity_type, activity.activity_type)
    contact_name = str(activity.contact) if activity.contact else "(no contact)"
    due_str = activity.due_date.strftime("%Y-%m-%d %H:%M") if activity.due_date else "no date"
    scheduled_time = activity.due_date.strftime("%Y-%m-%d %H:%M") if activity.due_date else "—"

    subject = f"Send {type_label} to {contact_name} at {due_str} — {scheduled_time}"

    # Recipient: email address, or LinkedIn URL if type is LinkedIn
    recipient = ""
    if activity.contact:
        if activity.activity_type == "linkedin":
            recipient = (activity.contact.linkedin or activity.contact.linkedin_url or "").strip()
        if not recipient and activity.contact.email:
            recipient = activity.contact.email
    recipient_display = recipient or "(none)"

    body_lines = [
        "Contact method: " + type_label,
        "Recipient: " + recipient_display,
        "Subject: " + (activity.subject or "(none)"),
        "Message:",
        activity.description or "(none)",
    ]
    body = "\n".join(body_lines)

    # Use console backend if explicitly configured (or as fallback when SMTP fails)
    use_console = getattr(settings, "TASK_MANAGER_EMAIL_BACKEND", "").lower() == "console"

    def _send_via_console() -> None:
        conn = get_connection("django.core.mail.backends.console.EmailBackend")
        conn.open()
        from django.core.mail import EmailMessage

        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[task_manager],
            connection=conn,
        )
        msg.send()
        conn.close()
        logger.info("Pending activity notification sent via console for Activity %s", activity.pk)

    if use_console:
        logger.info(
            "Sending pending activity notification via console for Activity %s (subject: %s)",
            activity.pk,
            subject[:80],
        )
        _send_via_console()
        return

    logger.info(
        "Sending pending activity notification to %s for Activity %s (subject: %s)",
        task_manager,
        activity.pk,
        subject[:80],
    )

    # Transient SMTP errors to retry
    retryable_errors = (
        smtplib.SMTPServerDisconnected,
        smtplib.SMTPConnectError,
        ConnectionRefusedError,
        ConnectionResetError,
        OSError,
    )
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            if attempt > 0:
                time.sleep(2**attempt)
            sent = send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[task_manager],
                fail_silently=False,
            )
            if sent:
                logger.info("Pending activity notification sent successfully for Activity %s", activity.pk)
                return
            logger.warning(
                "send_mail returned 0 for Activity %s; check EMAIL_* settings",
                activity.pk,
            )
            return
        except retryable_errors as e:
            if attempt < max_attempts - 1:
                logger.warning(
                    "SMTP error for Activity %s (attempt %s/%s): %s; retrying...",
                    activity.pk,
                    attempt + 1,
                    max_attempts,
                    e,
                )
            else:
                logger.warning(
                    "SMTP failed for Activity %s after %s attempts: %s; falling back to console",
                    activity.pk,
                    max_attempts,
                    e,
                )
                _send_via_console()
                return
        except Exception as e:
            logger.exception("Failed to notify task manager for Activity %s: %s", activity.pk, e)
            _send_via_console()


def _notify_task_manager_pending(activity: Activity) -> None:
    """Send email to TASK_MANAGER. Runs synchronously to avoid SMTP issues in background threads."""
    _send_pending_notification_email(activity)


def _send_newsletter_edition_notification(edition: NewsletterEdition) -> None:
    """Send email to TASK_MANAGER when a newsletter edition is added."""
    task_manager = getattr(settings, "TASK_MANAGER", None)
    if not task_manager:
        logger.warning(
            "TASK_MANAGER not configured; skipping newsletter edition notification for Edition %s",
            edition.pk,
        )
        return

    topic_label = edition.weekly_theme or "Newsletter"
    start_date = edition.scheduled_date.strftime("%Y-%m-%d") if edition.scheduled_date else "—"
    subject = f"Week {edition.week_number}: {topic_label} due on {start_date}"

    # Get all editions for this week (same plan, quarter, week_number)
    week_editions = list(
        NewsletterEdition.objects.filter(
            plan=edition.plan,
            quarter=edition.quarter,
            week_number=edition.week_number,
        )
    )
    week_editions.sort(key=lambda e: (e.week_number, (e.day_of_week or "Monday"), e.pk))

    # Build HTML table
    import html as html_module

    headers = ("Week", "Start Date", "Day", "Weekly Theme", "Daily Topic", "Notes", "Status", "URL")
    header_row = "".join(f"<th>{h}</th>" for h in headers)
    body_rows = []
    for e in week_editions:
        url_cell = f'<a href="{html_module.escape(e.url)}">{html_module.escape(e.url[:60])}</a>' if e.url else "—"
        cells = [
            html_module.escape(str(e.week_number)),
            html_module.escape(e.scheduled_date.strftime("%Y-%m-%d") if e.scheduled_date else "—"),
            html_module.escape(e.day_of_week or "—"),
            html_module.escape((e.weekly_theme or "—")[:80]),
            html_module.escape((e.weekly_theme or "—")[:80]),
            html_module.escape((e.notes or "—")[:50]),
            html_module.escape(e.get_status_display()),
            url_cell,
        ]
        body_rows.append("".join(f"<td>{c}</td>" for c in cells))
    table_rows = "".join(f"<tr>{r}</tr>" for r in body_rows)
    body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
table {{ border-collapse: collapse; font-family: sans-serif; font-size: 13px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
th {{ background: #f5f5f5; font-weight: 600; }}
</style></head>
<body>
<p><strong>Newsletter plan:</strong> {edition.plan} ({edition.quarter})</p>
<table>
<thead><tr>{header_row}</tr></thead>
<tbody>
{table_rows}
</tbody>
</table>
</body>
</html>"""

    use_console = getattr(settings, "TASK_MANAGER_EMAIL_BACKEND", "").lower() == "console"

    def _send_via_console() -> None:
        from django.core.mail import EmailMessage

        conn = get_connection("django.core.mail.backends.console.EmailBackend")
        conn.open()
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[task_manager],
            connection=conn,
        )
        msg.content_subtype = "html"
        msg.send()
        conn.close()
        logger.info("Newsletter edition notification sent via console for Edition %s", edition.pk)

    if use_console:
        _send_via_console()
        return

    logger.info(
        "Sending newsletter edition notification to %s for Edition %s (subject: %s)",
        task_manager,
        edition.pk,
        subject[:80],
    )
    retryable_errors = (
        smtplib.SMTPServerDisconnected,
        smtplib.SMTPConnectError,
        ConnectionRefusedError,
        ConnectionResetError,
        OSError,
    )
    from django.core.mail import EmailMessage

    for attempt in range(3):
        try:
            if attempt > 0:
                time.sleep(2**attempt)
            msg = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[task_manager],
            )
            msg.content_subtype = "html"
            sent = msg.send(fail_silently=False)
            if sent:
                logger.info("Newsletter edition notification sent for Edition %s", edition.pk)
                return
        except retryable_errors as e:
            if attempt < 2:
                logger.warning("SMTP error for Edition %s (attempt %s): %s; retrying...", edition.pk, attempt + 1, e)
            else:
                logger.warning("SMTP failed for Edition %s after 3 attempts: %s; falling back to console", edition.pk, e)
                _send_via_console()
                return
        except Exception as e:
            logger.exception("Failed to notify task manager for NewsletterEdition %s: %s", edition.pk, e)
            _send_via_console()
            return


def connect_pending_activity_signals():
    """Connect signals to notify TASK_MANAGER when an activity is Pending."""

    @receiver(pre_save, sender=Activity)
    def _capture_old_status(sender, instance, **kwargs):
        if instance.pk:
            try:
                old = Activity.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
                _activity_old_status.set(old)
            except Exception:
                _activity_old_status.set(None)
        else:
            _activity_old_status.set(None)

    @receiver(post_save, sender=Activity)
    def _on_activity_saved(sender, instance, created, **kwargs):
        if instance.status != "pending":
            return
        old_status = _activity_old_status.get()
        should_notify = created or (old_status is not None and old_status != "pending")
        if should_notify:
            logger.info(
                "Activity %s became pending (created=%s, old_status=%s); notifying task manager",
                instance.pk,
                created,
                old_status,
            )
            _notify_task_manager_pending(instance)


def connect_newsletter_edition_signals():
    """Connect signals to notify TASK_MANAGER when a newsletter edition is added."""

    @receiver(post_save, sender=NewsletterEdition)
    def _on_newsletter_edition_created(sender, instance, created, **kwargs):
        if created:
            logger.info("Newsletter edition %s created; notifying task manager", instance.pk)
            _send_newsletter_edition_notification(instance)
