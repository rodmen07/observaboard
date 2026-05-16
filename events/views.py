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
from .stream_publisher import publish_to_stream
from .tasks import classify_event, enqueue_classify_task

logger = logging.getLogger(__name__)


def _verify_cloud_tasks_token(auth_header: str) -> bool:
    """
    Verify the OIDC token Cloud Tasks attaches to callback requests.

    When CLOUD_TASKS_SA_EMAIL is not configured (local dev / CI) the check is
    skipped so tests can hit the endpoint without GCP credentials.
    """
    sa_email = getattr(django_settings, "CLOUD_TASKS_SA_EMAIL", "")
    if not sa_email:
        return True

    if not auth_header.startswith("Bearer "):
        return False

    token = auth_header[7:]
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        request = google.auth.transport.requests.Request()
        claims = google.oauth2.id_token.verify_oauth2_token(token, request)
        return claims.get("email") == sa_email
    except Exception:
        logger.exception("Cloud Tasks OIDC token verification failed")
        return False


@extend_schema(tags=["health"])
class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(summary="Health check", description="Returns status of API and database.")
    def get(self, request):
        checks = {"api": "ok"}

        try:
            connection.ensure_connection()
            checks["database"] = "ok"
        except Exception:
            logger.exception("Health check: database connection failed")
            checks["database"] = "error"

        overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
        status_code = 200 if overall == "ok" else 503
        return Response({"status": overall, **checks}, status=status_code)


@extend_schema(tags=["ingest"])
class IngestView(APIView):
    """
    POST /api/ingest/
    Accepts webhook payloads. Authenticated via API key or JWT.
    Stores the raw event and enqueues it for async classification via Cloud Tasks.
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

        # Enqueue async classification via Cloud Tasks (falls back to inline in dev).
        enqueue_classify_task(str(event.id))

        logger.info("Ingested event %s from %s (%s)", event.id, data["source"], data["event_type"])

        return Response(
            {"id": str(event.id), "status": "accepted"},
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema(tags=["tasks"])
class ClassifyCallbackView(APIView):
    """
    POST /api/tasks/classify/
    Invoked by Cloud Tasks. Verifies the OIDC token, classifies the event,
    and publishes it to event-stream-service.
    """
    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not _verify_cloud_tasks_token(auth_header):
            logger.warning("Cloud Tasks callback rejected: invalid token")
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        event_id = request.data.get("event_id")
        if not event_id:
            return Response({"error": "Missing event_id"}, status=status.HTTP_400_BAD_REQUEST)

        classify_event(str(event_id))

        if django_settings.EVENT_STREAM_URL:
            try:
                event = Event.objects.get(id=event_id)
                publish_to_stream(
                    event,
                    stream_url=django_settings.EVENT_STREAM_URL,
                    jwt_secret=django_settings.EVENT_STREAM_JWT_SECRET,
                )
            except Event.DoesNotExist:
                logger.warning("Classify callback: event %s not found for stream publish", event_id)

        return Response({"classified": str(event_id)}, status=status.HTTP_200_OK)


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
