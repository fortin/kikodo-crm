from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crm"

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save
        from django.dispatch import receiver

        from .audit import connect_signals
        from .models import UserProfile
        from .signals import connect_newsletter_edition_signals, connect_pending_activity_signals
        from .templatetags import crm_extras  # noqa: F401 - ensure tag library is registered

        connect_signals()
        connect_pending_activity_signals()
        connect_newsletter_edition_signals()

        @receiver(post_save, sender=get_user_model())
        def ensure_user_profile(sender, instance, created, **kwargs):
            if created and not hasattr(instance, "profile"):
                UserProfile.objects.get_or_create(user=instance)
