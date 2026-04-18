"""Custom template filters for the CRM app."""

from django import template
from django.utils.safestring import mark_safe

try:
    import markdown
except ImportError:
    markdown = None

register = template.Library()


@register.filter
def get_item(d, key):
    """Get dict item by key. Returns empty string if missing."""
    return d.get(key, "") if d else ""


@register.filter
def markdown_to_html(value):
    """Convert Markdown text to HTML. Returns empty string if value is falsy."""
    if not value:
        return ""
    if markdown is None:
        return mark_safe(str(value).replace("\n", "<br>"))
    html = markdown.markdown(str(value), extensions=["nl2br"])
    return mark_safe(html)
