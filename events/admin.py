from django.contrib import admin
from django.utils.html import format_html
from .models import Event, ApiKey


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["id", "source", "event_type", "category", "severity_badge", "classified", "created_at"]
    list_filter = ["category", "severity", "classified", "source"]
    search_fields = ["source", "event_type", "summary"]
    readonly_fields = ["id", "classified", "category", "severity", "summary", "search_vector", "created_at", "updated_at"]
    ordering = ["-created_at"]

    _severity_colors = {
        "low":      "#6b7280",
        "medium":   "#d97706",
        "high":     "#dc2626",
        "critical": "#7c3aed",
    }

    @admin.display(description="Severity")
    def severity_badge(self, obj):
        color = self._severity_colors.get(obj.severity, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color,
            obj.severity.upper(),
        )

    def has_add_permission(self, request):
        return False  # events come in via the API only


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "masked_key", "is_active", "created_at", "last_used_at"]
    list_filter = ["is_active"]
    readonly_fields = ["key", "created_at", "last_used_at"]
    ordering = ["-created_at"]

    @admin.display(description="Key")
    def masked_key(self, obj):
        return f"{obj.key[:8]}…{'*' * 24}"
