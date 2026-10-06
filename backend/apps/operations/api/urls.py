from django.urls import path

from .views import RenewalCalendarView, SubscriptionDetailView, SubscriptionListCreateView

urlpatterns = [
    path(
        "operations/subscriptions/",
        SubscriptionListCreateView.as_view(),
        name="subscription-list",
    ),
    path(
        "operations/subscriptions/<uuid:object_id>/",
        SubscriptionDetailView.as_view(),
        name="subscription-detail",
    ),
    path("operations/renewals/", RenewalCalendarView.as_view(), name="renewal-calendar"),
]
