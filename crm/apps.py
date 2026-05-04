from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crm"

    def ready(self):
        import logging

        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save
        from django.dispatch import receiver

        from .audit import connect_signals
        from .models import UserProfile
        from .signals import connect_newsletter_edition_signals, connect_pending_activity_signals
        from .templatetags import crm_extras  # noqa: F401 - ensure tag library is registered

        logger = logging.getLogger("crm")

        connect_signals()
        connect_pending_activity_signals()
        connect_newsletter_edition_signals()

        @receiver(post_save, sender=get_user_model())
        def ensure_user_profile(sender, instance, created, **kwargs):
            if created and not hasattr(instance, "profile"):
                UserProfile.objects.get_or_create(user=instance)

        @receiver(post_save, sender=get_user_model())
        def notify_new_user_registered(sender, instance, created, raw=False, **kwargs):
            """
            Notify DEFAULT_FROM_EMAIL when a new User is created.
            Intended for "new user registration" events; safe to run for any user creation.
            """
            if raw or not created:
                return

            try:
                from django.conf import settings
                from django.core.mail import EmailMessage

                to_email = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
                if not to_email:
                    logger.warning("DEFAULT_FROM_EMAIL not configured; skipping new user notification")
                    return

                username = getattr(instance, "get_username", lambda: None)() or getattr(
                    instance, "username", ""
                )
                subject = f"New user registered: {username or instance.pk}"

                body_lines = [
                    "A new user was created.",
                    "",
                    f"User ID: {getattr(instance, 'pk', None)}",
                    f"Username: {username}",
                    f"Email: {getattr(instance, 'email', '')}",
                    f"First name: {getattr(instance, 'first_name', '')}",
                    f"Last name: {getattr(instance, 'last_name', '')}",
                    f"Is staff: {getattr(instance, 'is_staff', False)}",
                    f"Is superuser: {getattr(instance, 'is_superuser', False)}",
                    f"Is active: {getattr(instance, 'is_active', False)}",
                    f"Date joined: {getattr(instance, 'date_joined', '')}",
                ]
                body = "\n".join(body_lines)

                msg = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=to_email,
                    to=[to_email],
                )
                msg.send(fail_silently=False)
            except Exception as e:
                # Never block registration / user creation on a notification email.
                logger.exception("Failed to send new user notification email: %s", e)
