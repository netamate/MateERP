from django.urls import path

from .email_views import (
    DirectEmailCancelView,
    DirectEmailListCreateView,
    DirectEmailSendView,
)
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
    path(
        "notifications/email/",
        DirectEmailListCreateView.as_view(),
        name="direct-email-list-create",
    ),
    path(
        "notifications/email/<uuid:notification_id>/send/",
        DirectEmailSendView.as_view(),
        name="direct-email-send",
    ),
    path(
        "notifications/email/<uuid:notification_id>/cancel/",
        DirectEmailCancelView.as_view(),
        name="direct-email-cancel",
    ),
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
