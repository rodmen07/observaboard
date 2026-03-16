from django.urls import path
from . import views

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("ingest/", views.IngestView.as_view(), name="ingest"),
    path("events/", views.EventListView.as_view(), name="event-list"),
    path("events/search/", views.EventSearchView.as_view(), name="event-search"),
    path("events/<uuid:pk>/", views.EventDetailView.as_view(), name="event-detail"),
    path("keys/", views.ApiKeyListCreateView.as_view(), name="apikey-list"),
    path("keys/<int:pk>/", views.ApiKeyDetailView.as_view(), name="apikey-detail"),
]
