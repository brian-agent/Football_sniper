from django.urls import path
from .views import trigger_snipe_view, health_check

urlpatterns = [
    path("trigger/", trigger_snipe_view, name="trigger_snipe"),
    path("health/", health_check, name="health_check"),
]