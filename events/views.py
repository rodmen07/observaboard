from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import Event, ApiKey
from .serializers import EventSerializer, IngestSerializer, ApiKeySerializer
from .tasks import classify_event


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class IngestView(APIView):
    """
    POST /api/ingest/
    Accepts webhook payloads. Authenticated via API key or JWT.
    Immediately stores the raw event, then enqueues async classification.
    """
    permission_classes = [IsAuthenticated]

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

        return Response(
            {"id": str(event.id), "status": "accepted"},
            status=status.HTTP_202_ACCEPTED,
        )


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


class EventDetailView(RetrieveAPIView):
    """GET /api/events/<uuid>/"""
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    queryset = Event.objects.all()


class EventSearchView(ListAPIView):
    """
    GET /api/events/search/?q=<query>
    Full-text search over source, event_type, summary, and raw payload text.
    Ranked by relevance.
    """
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        if not q:
            return Event.objects.none()

        query = SearchQuery(q)
        return (
            Event.objects.filter(search_vector=query)
            .annotate(rank=SearchRank(F("search_vector"), query))
            .order_by("-rank", "-created_at")
        )


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
