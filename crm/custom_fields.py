"""Helpers for CustomField/CustomFieldValue (analytics) in CRM entity detail/edit."""

from django.contrib.contenttypes.models import ContentType

from analytics.models import CustomField, CustomFieldValue


def get_custom_fields_for_entity(entity_type):
    """Return active CustomFields for entity_type (contact, company, deal)."""
    return list(
        CustomField.objects.filter(entity_type=entity_type, is_active=True).order_by(
            "order", "name"
        )
    )


def get_custom_field_values(instance):
    """Return dict custom_field_id -> CustomFieldValue (or None) for this instance."""
    if instance is None or not instance.pk:
        return {}
    ct = ContentType.objects.get_for_model(instance)
    values = CustomFieldValue.objects.filter(
        content_type=ct, object_id=instance.pk
    ).select_related("custom_field")
    return {v.custom_field_id: v for v in values}


def get_value_display(cfv):
    """Return display value for a CustomFieldValue."""
    if cfv is None:
        return ""
    return cfv.get_value()


def save_custom_field_values(instance, post_data, prefix="custom_"):
    """Save CustomFieldValue from POST data. Keys must be custom_<field_id>."""
    if instance is None or not instance.pk:
        return
    ct = ContentType.objects.get_for_model(instance)
    fields = get_custom_fields_for_entity(instance._meta.model_name)
    for cf in fields:
        key = f"{prefix}{cf.id}"
        raw = post_data.get(key)
        cfv, _ = CustomFieldValue.objects.get_or_create(
            custom_field=cf,
            content_type=ct,
            object_id=instance.pk,
            defaults={},
        )
        if cf.field_type == "text":
            cfv.text_value = (raw or "").strip()
        elif cf.field_type == "number":
            try:
                cfv.number_value = float(raw) if raw else None
            except (TypeError, ValueError):
                cfv.number_value = None
        elif cf.field_type == "date":
            cfv.date_value = raw if raw else None
        elif cf.field_type == "boolean":
            cfv.boolean_value = raw in ("on", "true", "1", "yes")
        elif cf.field_type in ("select", "multiselect"):
            if cf.field_type == "select":
                cfv.json_value = [raw] if raw else []
            else:
                raw_list = (
                    post_data.getlist(key)
                    if hasattr(post_data, "getlist")
                    else ([raw] if raw else [])
                )
                cfv.json_value = raw_list if isinstance(raw_list, list) else [raw_list]
        elif cf.field_type in ("url", "email"):
            cfv.text_value = (raw or "").strip()
        cfv.save()
