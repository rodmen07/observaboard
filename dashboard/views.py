from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.paginator import Paginator
from django.db.models import Count, F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from events.models import ApiKey, Event


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.POST.get("next") or request.GET.get("next") or "dashboard:index"
            # Only redirect to safe internal URLs
            if next_url.startswith("/"):
                return redirect(next_url)
            return redirect("dashboard:index")
        # Return form with error
        return render(request, "dashboard/login.html", {"form": {"errors": True}, "next": request.GET.get("next")})

    return render(request, "dashboard/login.html", {"next": request.GET.get("next")})


def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("dashboard:login")


@login_required
def index(request):
    categories = (
        Event.objects.exclude(category="")
        .values("category")
        .annotate(count=Count("id"))
        .order_by("category")
    )
    severities = (
        Event.objects.values("severity")
        .annotate(count=Count("id"))
        .order_by("severity")
    )
    recent_events = Event.objects.order_by("-created_at")[:10]
    total_events = Event.objects.count()

    return render(request, "dashboard/index.html", {
        "active_page": "index",
        "categories": categories,
        "severities": severities,
        "recent_events": recent_events,
        "total_events": total_events,
    })


@login_required
def events_list(request):
    qs = Event.objects.all()

    filters = {
        "q": request.GET.get("q", "").strip(),
        "source": request.GET.get("source", ""),
        "category": request.GET.get("category", ""),
        "severity": request.GET.get("severity", ""),
    }

    if filters["source"]:
        qs = qs.filter(source=filters["source"])
    if filters["category"]:
        qs = qs.filter(category=filters["category"])
    if filters["severity"]:
        qs = qs.filter(severity=filters["severity"])
    if filters["q"]:
        query = SearchQuery(filters["q"])
        qs = (
            qs.filter(search_vector=query)
            .annotate(rank=SearchRank(F("search_vector"), query))
            .order_by("-rank", "-created_at")
        )

    total_count = qs.count()
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    sources = Event.objects.values_list("source", flat=True).distinct().order_by("source")

    context = {
        "active_page": "events",
        "page_obj": page_obj,
        "total_count": total_count,
        "sources": sources,
        "category_choices": Event.CATEGORY_CHOICES,
        "severity_choices": Event.SEVERITY_CHOICES,
        "current_filters": filters,
    }

    if request.htmx:
        return render(request, "dashboard/_events_table.html", context)

    return render(request, "dashboard/events_list.html", context)


@login_required
def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    return render(request, "dashboard/event_detail.html", {
        "active_page": "events",
        "event": event,
    })


@login_required
def keys_list(request):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    keys = ApiKey.objects.all()
    return render(request, "dashboard/keys.html", {
        "active_page": "keys",
        "keys": keys,
    })


@login_required
def key_create(request):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if name:
            key = ApiKey(name=name)
            key.save()
            return render(request, "dashboard/_key_row.html", {
                "key": key,
                "show_full_key": True,
            })

    return HttpResponse(status=400)


@login_required
def key_toggle(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    key = get_object_or_404(ApiKey, pk=pk)
    key.is_active = not key.is_active
    key.save(update_fields=["is_active"])
    return render(request, "dashboard/_key_row.html", {"key": key})


@login_required
def key_delete(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    key = get_object_or_404(ApiKey, pk=pk)
    key.delete()
    return HttpResponse("")
