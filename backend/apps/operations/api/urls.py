from django.urls import path

from .views import (
    RenewalCalendarView,
    SubscriptionDetailView,
    SubscriptionListCreateView,
    SubscriptionMarkPaidView,
    SubscriptionPaymentHistoryView,
)

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
    path(
        "operations/subscriptions/<uuid:object_id>/payments/",
        SubscriptionPaymentHistoryView.as_view(),
        name="subscription-payment-history",
    ),
    path(
        "operations/subscriptions/<uuid:object_id>/mark-paid/",
        SubscriptionMarkPaidView.as_view(),
        name="subscription-mark-paid",
    ),
    path("operations/renewals/", RenewalCalendarView.as_view(), name="renewal-calendar"),
]
