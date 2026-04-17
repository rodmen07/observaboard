import logging

from django.conf import settings as django_settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import connection
from django.db.models import F
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ApiKey, Event
from .serializers import ApiKeySerializer, EventSerializer, IngestSerializer
from .tasks import classify_event

logger = logging.getLogger(__name__)


@extend_schema(tags=["health"])
class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(summary="Health check", description="Returns status of API, database, and Redis.")
    def get(self, request):
        checks = {"api": "ok"}

        try:
            connection.ensure_connection()
            checks["database"] = "ok"
        except Exception:
            logger.exception("Health check: database connection failed")
            checks["database"] = "error"

        try:
            import redis
            r = redis.from_url(django_settings.CELERY_BROKER_URL)
            r.ping()
            checks["redis"] = "ok"
        except Exception:
            logger.exception("Health check: Redis ping failed")
            checks["redis"] = "error"

        overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
        status_code = 200 if overall == "ok" else 503
        return Response({"status": overall, **checks}, status=status_code)


@extend_schema(tags=["ingest"])
class IngestView(APIView):
    """
    POST /api/ingest/
    Accepts webhook payloads. Authenticated via API key or JWT.
    Immediately stores the raw event, then enqueues async classification.
    """
    permission_classes = [IsAuthenticated]
    throttle_scope = "ingest"

    @extend_schema(request=IngestSerializer, responses={202: EventSerializer}, summary="Ingest event")
    def post(self, request):
        serializer = IngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        event = Event.objects.create(
            source=data["source"],
            event_type=data["event_type"],
            raw_payload=data["payload"],
        )

        classify_event.delay(str(event.id))

        logger.info("Ingested event %s from %s (%s)", event.id, data["source"], data["event_type"])

        return Response(
            {"id": str(event.id), "status": "accepted"},
            status=status.HTTP_202_ACCEPTED,
        )


@method_decorator(cache_control(private=True, max_age=30), name="dispatch")
@extend_schema(tags=["events"])
class EventListView(ListAPIView):
    """GET /api/events/  — paginated list, filterable by source/category/severity."""
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Event.objects.all()
        for param in ("source", "category", "severity", "event_type"):
            value = self.request.query_params.get(param)
            if value:
                qs = qs.filter(**{param: value})
        if classified := self.request.query_params.get("classified"):
            qs = qs.filter(classified=classified.lower() == "true")
        return qs


@method_decorator(cache_control(private=True, max_age=30), name="dispatch")
@extend_schema(tags=["events"])
class EventDetailView(RetrieveAPIView):
    """GET /api/events/<uuid>/"""
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    queryset = Event.objects.all()


@extend_schema(
    tags=["events"],
    parameters=[OpenApiParameter("q", str, description="Full-text search query")],
)
class EventSearchView(ListAPIView):
    """
    GET /api/events/search/?q=<query>
    Full-text search over source, event_type, summary, and raw payload text.
    Ranked by relevance.
    """
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    throttle_scope = "search"

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()[:200]
        if not q:
            return Event.objects.none()

        query = SearchQuery(q)
        return (
            Event.objects.filter(search_vector=query)
            .annotate(rank=SearchRank(F("search_vector"), query))
            .order_by("-rank", "-created_at")
        )


@extend_schema(tags=["api-keys"])
class ApiKeyListCreateView(APIView):
    """GET/POST /api/keys/  — admin only."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        keys = ApiKey.objects.all()
        return Response(ApiKeySerializer(keys, many=True).data)

    def post(self, request):
        serializer = ApiKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        api_key = serializer.save()
        return Response(ApiKeySerializer(api_key).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["api-keys"])
class ApiKeyDetailView(APIView):
    """PATCH/DELETE /api/keys/<pk>/  — admin only (revoke / rename)."""
    permission_classes = [IsAdminUser]

    def _get_key(self, pk):
        try:
            return ApiKey.objects.get(pk=pk)
        except ApiKey.DoesNotExist:
            return None

    def patch(self, request, pk):
        key = self._get_key(pk)
        if key is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ApiKeySerializer(key, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        key = self._get_key(pk)
        if key is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        key.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
