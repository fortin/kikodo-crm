"""
Audit logging for Contact, Company, Deal, Activity.
Uses middleware to set current user and Django signals to log create/update/delete.
"""

import contextvars
import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Activity, AuditLog, Company, Contact, Deal

logger = logging.getLogger(__name__)

_audit_user = contextvars.ContextVar("audit_user", default=None)
_audit_old = contextvars.ContextVar("audit_old", default=None)


def _get_audit_old():
    if _audit_old.get() is None:
        _audit_old.set({})
    return _audit_old.get()


# Fields to capture per model (avoid huge payloads)
_AUDIT_FIELDS = {
    "contact": [
        "first_name",
        "last_name",
        "email",
        "status",
        "company_id",
        "owner_id",
        "is_active",
    ],
    "company": ["name", "industry", "owner_id", "is_active"],
    "deal": [
        "name",
        "amount",
        "stage",
        "pipeline_id",
        "pipeline_stage_id",
        "contact_id",
        "company_id",
        "owner_id",
        "is_active",
    ],
    "activity": [
        "activity_type",
        "subject",
        "contact_id",
        "company_id",
        "deal_id",
        "owner_id",
        "status",
    ],
}


def _serialize(instance, model_label):
    fields = _AUDIT_FIELDS.get(model_label, [])
    data = {}
    for f in fields:
        if hasattr(instance, f):
            try:
                v = getattr(instance, f)
                if v is None:
                    data[f] = None
                elif hasattr(v, "pk"):
                    data[f] = v.pk
                else:
                    data[f] = str(v)
            except Exception:
                pass
    return data


def _model_label(instance):
    return instance._meta.label_lower


def _log(action, model_name, object_id, object_repr, old_values=None, new_values=None):
    user = _audit_user.get()
    AuditLog.objects.create(
        user_id=user.pk if user and hasattr(user, "pk") else None,
        action=action,
        model_name=model_name,
        object_id=object_id,
        object_repr=(object_repr or "")[:255],
        old_values=old_values or {},
        new_values=new_values or {},
    )
    event_name = f"{model_name.split('.')[-1]}.{action}"
    from .webhooks import build_webhook_payload, dispatch_webhooks

    payload = build_webhook_payload(
        event_name,
        model_name,
        object_id,
        object_repr or "",
        old_values or {},
        new_values or {},
    )
    dispatch_webhooks(event_name, payload)


def _connect(model_class, model_label_key):
    model_label = model_class._meta.label_lower

    @receiver(pre_save, sender=model_class)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            try:
                old = model_class.objects.filter(pk=instance.pk).first()
                if old:
                    _get_audit_old()[(model_label, instance.pk)] = _serialize(
                        old, model_label_key
                    )
            except Exception as e:
                logger.warning("Audit pre_save %s: %s", model_label, e)

    @receiver(post_save, sender=model_class)
    def _post_save(sender, instance, created, **kwargs):
        try:
            key = (model_label, instance.pk)
            old_values = _get_audit_old().pop(key, None)
            new_values = _serialize(instance, model_label_key)
            if created:
                _log(
                    "create",
                    model_label,
                    instance.pk,
                    str(instance),
                    old_values={},
                    new_values=new_values,
                )
            else:
                _log(
                    "update",
                    model_label,
                    instance.pk,
                    str(instance),
                    old_values=old_values or {},
                    new_values=new_values,
                )
        except Exception as e:
            logger.warning("Audit post_save %s: %s", model_label, e)

    @receiver(post_delete, sender=model_class)
    def _post_delete(sender, instance, **kwargs):
        try:
            old_values = _serialize(instance, model_label_key)
            _log(
                "delete",
                model_label,
                instance.pk,
                str(instance),
                old_values=old_values,
                new_values={},
            )
        except Exception as e:
            logger.warning("Audit post_delete %s: %s", model_label, e)


def connect_signals():
    _connect(Contact, "contact")
    _connect(Company, "company")
    _connect(Deal, "deal")
    _connect(Activity, "activity")


class AuditMiddleware:
    """Set current user in context so audit signals can attribute actions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        # Force eager evaluation of SimpleLazyObject while still in the sync thread.
        # Without this, asgiref's _restore_context calls ContextVar.get() in the async
        # event loop, which triggers the lazy DB query and raises SynchronousOnlyOperation.
        if user is not None:
            try:
                bool(user.is_authenticated)
            except Exception:
                pass
        _audit_user.set(user)
        _audit_old.set({})
        try:
            return self.get_response(request)
        finally:
            _audit_old.set(None)
            _audit_user.set(None)
