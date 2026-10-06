from django.urls import path

from .views import (
    NotificationDeliveryListView,
    NotificationIntegrationEmailTestView,
    NotificationIntegrationHermesTestView,
    NotificationIntegrationSettingsView,
    NotificationListView,
    NotificationReadAllView,
    NotificationReadView,
)

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path(
        "notifications/<uuid:notification_id>/read/",
        NotificationReadView.as_view(),
        name="notification-read",
    ),
    path(
        "notifications/read-all/",
        NotificationReadAllView.as_view(),
        name="notification-read-all",
    ),
    path(
        "notifications/deliveries/",
        NotificationDeliveryListView.as_view(),
        name="notification-delivery-list",
    ),
    path(
        "notifications/integrations/",
        NotificationIntegrationSettingsView.as_view(),
        name="notification-integration-settings",
    ),
    path(
        "notifications/integrations/test-email/",
        NotificationIntegrationEmailTestView.as_view(),
        name="notification-integration-test-email",
    ),
    path(
        "notifications/integrations/test-hermes/",
        NotificationIntegrationHermesTestView.as_view(),
        name="notification-integration-test-hermes",
    ),
]
