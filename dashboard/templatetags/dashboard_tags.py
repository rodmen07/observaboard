import json

from django import template

register = template.Library()

SEVERITY_CLASSES = {
    "low": "bg-gray-500",
    "medium": "bg-amber-500",
    "high": "bg-red-600",
    "critical": "bg-purple-600",
}

CATEGORY_CLASSES = {
    "deployment": "bg-blue-600",
    "security": "bg-red-600",
    "alert": "bg-orange-500",
    "metric": "bg-emerald-600",
    "info": "bg-gray-500",
}


@register.filter
def pretty_json(value):
    """Render a dict/JSON value as indented JSON string."""
    try:
        return json.dumps(value, indent=2, default=str)
    except (TypeError, ValueError):
        return str(value)


@register.filter
def severity_class(value):
    """Return Tailwind CSS class for a severity level."""
    return SEVERITY_CLASSES.get(value, "bg-gray-500")


@register.filter
def category_class(value):
    """Return Tailwind CSS class for a category."""
    return CATEGORY_CLASSES.get(value, "bg-gray-500")


@register.filter
def mask_key(value):
    """Show first 8 chars of an API key, mask the rest."""
    if len(value) > 8:
        return f"{value[:8]}{'*' * 24}"
    return value
