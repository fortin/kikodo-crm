"""
Generic read-only database access for the AI chatbot and MCP server.

Exposes list_models, describe_model, query_records, get_record, and count_records
so the assistant can query any model in the crm and analytics apps.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import Q

logger = logging.getLogger("crm")

QUERYABLE_APPS = ("crm", "analytics")
MAX_QUERY_LIMIT = 50
MAX_FILTER_DEPTH = 3

ALLOWED_LOOKUPS = frozenset({
    "exact", "iexact", "contains", "icontains", "in", "gt", "gte", "lt", "lte",
    "isnull", "startswith", "istartswith", "endswith", "iendswith", "range",
})

REDACT_FIELD_NAMES = frozenset({"password"})

DB_TOOL_SCHEMAS = [
    {
        "name": "list_models",
        "description": (
            "List all CRM database models you can query. "
            "Call this first when unsure which model holds the data."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "describe_model",
        "description": (
            "Get field names, types, and choices for a model. "
            "Use before query_records when filter fields are unclear."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Model name, e.g. NewsletterIssue or crm.NewsletterIssue",
                },
            },
            "required": ["model"],
        },
    },
    {
        "name": "query_records",
        "description": (
            "Search and list records from any CRM model. "
            "Filters use Django ORM syntax (e.g. status='published', title__icontains='weekly'). "
            "Use describe_model to see valid field names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "filters": {
                    "type": "object",
                    "description": "Field lookups, e.g. {\"status\": \"draft\", \"title__icontains\": \"Q1\"}",
                    "additionalProperties": True,
                },
                "search": {
                    "type": "string",
                    "description": "Optional free-text search across CharField/TextField columns",
                },
                "order_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Sort fields, prefix with - for descending (e.g. [\"-created_at\"])",
                },
                "limit": {"type": "integer", "default": 20},
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional subset of fields to return per record",
                },
            },
            "required": ["model"],
        },
    },
    {
        "name": "get_record",
        "description": "Fetch a single record by primary key from any CRM model.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "id": {"type": "integer"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional subset of fields to return",
                },
            },
            "required": ["model", "id"],
        },
    },
    {
        "name": "count_records",
        "description": "Count records in a model, optionally with the same filters as query_records.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "filters": {"type": "object", "additionalProperties": True},
                "search": {"type": "string"},
            },
            "required": ["model"],
        },
    },
]


def _queryable_models() -> list[type[models.Model]]:
    result = []
    for app_label in QUERYABLE_APPS:
        for model in apps.get_app_config(app_label).get_models():
            result.append(model)
    return sorted(result, key=lambda m: (m._meta.app_label, m.__name__))


def _model_label(model: type[models.Model]) -> str:
    return f"{model._meta.app_label}.{model.__name__}"


def resolve_model(model_name: str) -> type[models.Model]:
    """Resolve a model name like 'NewsletterIssue' or 'crm.NewsletterIssue'."""
    name = (model_name or "").strip()
    if not name:
        raise ValueError("Model name is required")

    if "." in name:
        app_label, class_name = name.split(".", 1)
        return apps.get_model(app_label, class_name)

    matches = [
        m for m in _queryable_models()
        if m.__name__.lower() == name.lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        labels = ", ".join(_model_label(m) for m in matches)
        raise ValueError(f"Ambiguous model '{name}'. Use one of: {labels}")

    raise ValueError(
        f"Unknown model '{name}'. Call list_models to see available models."
    )


def _field_type_name(field: models.Field) -> str:
    internal = field.get_internal_type()
    if isinstance(field, models.ForeignKey):
        related = field.related_model
        related_label = _model_label(related) if related else "unknown"
        return f"ForeignKey -> {related_label}"
    if isinstance(field, models.ManyToManyField):
        related = field.related_model
        related_label = _model_label(related) if related else "unknown"
        return f"ManyToMany -> {related_label}"
    return internal


def _validate_filter_key(model: type[models.Model], key: str) -> None:
    parts = key.split("__")
    if len(parts) > MAX_FILTER_DEPTH:
        raise ValueError(f"Filter key too deep: {key}")

    lookup = parts[-1] if len(parts) > 1 and parts[-1] in ALLOWED_LOOKUPS else None
    field_parts = parts[:-1] if lookup else parts
    if lookup and len(parts) == 1:
        lookup = None
        field_parts = parts

    current_model = model
    for i, part in enumerate(field_parts):
        is_last = i == len(field_parts) - 1
        try:
            field = current_model._meta.get_field(part)
        except FieldDoesNotExist as exc:
            raise ValueError(f"Unknown field '{part}' on {_model_label(current_model)}") from exc

        if isinstance(field, models.ForeignKey) and not is_last:
            current_model = field.related_model
            continue
        if not is_last:
            raise ValueError(f"Cannot traverse '{part}' on {_model_label(current_model)}")


def _coerce_filter_value(value: Any) -> Any:
    if isinstance(value, str):
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == "null":
            return None
    return value


def _apply_filters(qs, model: type[models.Model], filters: dict | None, search: str | None):
    if filters:
        clean = {}
        for key, value in filters.items():
            _validate_filter_key(model, key)
            if isinstance(value, list):
                clean[key] = [_coerce_filter_value(v) for v in value]
            else:
                clean[key] = _coerce_filter_value(value)
        qs = qs.filter(**clean)

    if search:
        search = search.strip()
        if search:
            q = Q()
            for field in model._meta.get_fields():
                if not getattr(field, "concrete", False):
                    continue
                if isinstance(field, (models.CharField, models.TextField, models.EmailField, models.SlugField)):
                    q |= Q(**{f"{field.name}__icontains": search})
            if q:
                qs = qs.filter(q)
    return qs


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, models.Model):
        return {"id": value.pk, "repr": str(value)}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, bytes):
        return "<bytes>"
    return value


def serialize_instance(
    obj: models.Model,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {"id": obj.pk}
    opts = obj._meta

    for field in opts.get_fields():
        if not getattr(field, "concrete", False):
            continue
        if field.many_to_many or field.one_to_many:
            continue
        name = field.name
        if name in REDACT_FIELD_NAMES:
            data[name] = "<redacted>"
            continue
        if fields and name not in fields:
            continue
        try:
            data[name] = _serialize_value(getattr(obj, name))
        except Exception:
            data[name] = None

    if fields:
        # Always include requested fields even if empty on model
        for name in fields:
            if name not in data and name != "id":
                data[name] = _serialize_value(getattr(obj, name, None))

    return data


def _describe_model(model: type[models.Model]) -> dict[str, Any]:
    fields = []
    for field in model._meta.get_fields():
        if not getattr(field, "concrete", False):
            continue
        if field.many_to_many or field.one_to_many:
            continue
        info = {
            "name": field.name,
            "type": _field_type_name(field),
            "required": not getattr(field, "blank", True) and not getattr(field, "null", False),
        }
        if getattr(field, "choices", None):
            info["choices"] = [c[0] for c in field.choices]
        if getattr(field, "help_text", ""):
            info["help_text"] = str(field.help_text)
        fields.append(info)

    doc = (model.__doc__ or "").strip().split("\n")[0]
    return {
        "model": _model_label(model),
        "verbose_name": str(model._meta.verbose_name),
        "description": doc,
        "fields": fields,
    }


def handle_list_models(_arguments: dict) -> dict[str, Any]:
    items = []
    for model in _queryable_models():
        doc = (model.__doc__ or "").strip().split("\n")[0]
        items.append({
            "model": _model_label(model),
            "name": model.__name__,
            "verbose_name": str(model._meta.verbose_name_plural or model._meta.verbose_name),
            "description": doc,
            "field_count": len([
                f for f in model._meta.get_fields()
                if getattr(f, "concrete", False) and not f.many_to_many and not f.one_to_many
            ]),
        })
    return {"models": items, "count": len(items)}


def handle_describe_model(arguments: dict) -> dict[str, Any]:
    model = resolve_model(arguments["model"])
    return _describe_model(model)


def handle_query_records(arguments: dict) -> dict[str, Any]:
    model = resolve_model(arguments["model"])
    limit = min(int(arguments.get("limit", 20)), MAX_QUERY_LIMIT)
    fields = arguments.get("fields")
    order_by = arguments.get("order_by") or ["-pk"]

    qs = model.objects.all()
    qs = _apply_filters(qs, model, arguments.get("filters"), arguments.get("search"))

    if order_by:
        qs = qs.order_by(*order_by)

    records = [serialize_instance(obj, fields) for obj in qs[:limit]]
    return {
        "model": _model_label(model),
        "count_returned": len(records),
        "limit": limit,
        "records": records,
    }


def handle_get_record(arguments: dict) -> dict[str, Any]:
    model = resolve_model(arguments["model"])
    fields = arguments.get("fields")
    try:
        obj = model.objects.get(pk=arguments["id"])
    except model.DoesNotExist:
        return {"error": f"{model.__name__} with id={arguments['id']} not found"}
    return {
        "model": _model_label(model),
        "record": serialize_instance(obj, fields),
    }


def handle_count_records(arguments: dict) -> dict[str, Any]:
    model = resolve_model(arguments["model"])
    qs = model.objects.all()
    qs = _apply_filters(qs, model, arguments.get("filters"), arguments.get("search"))
    return {
        "model": _model_label(model),
        "count": qs.count(),
    }


_HANDLERS = {
    "list_models": handle_list_models,
    "describe_model": handle_describe_model,
    "query_records": handle_query_records,
    "get_record": handle_get_record,
    "count_records": handle_count_records,
}


def dispatch(name: str, arguments: dict) -> dict[str, Any]:
    handler = _HANDLERS.get(name)
    if not handler:
        return {"error": f"Unknown database tool: {name}"}
    try:
        return handler(arguments or {})
    except Exception as exc:
        logger.warning("ai_db tool %s failed: %s", name, exc)
        return {"error": str(exc)}


def dispatch_json(name: str, arguments: dict) -> str:
    return json.dumps(dispatch(name, arguments), indent=2, default=str)
