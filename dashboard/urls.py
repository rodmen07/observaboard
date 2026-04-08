from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("events/", views.events_list, name="events_list"),
    path("events/<uuid:pk>/", views.event_detail, name="event_detail"),
    path("keys/", views.keys_list, name="keys_list"),
    path("keys/create/", views.key_create, name="key_create"),
    path("keys/<int:pk>/toggle/", views.key_toggle, name="key_toggle"),
    path("keys/<int:pk>/delete/", views.key_delete, name="key_delete"),
]
