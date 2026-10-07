from django.urls import path

from .views import (
    RenewalCalendarView,
    ServiceAccountDetailView,
    ServiceAccountListCreateView,
    SubscriptionDetailView,
    SubscriptionListCreateView,
    SubscriptionMarkPaidView,
    SubscriptionPaymentHistoryView,
    VendorServiceDetailView,
    VendorServiceListCreateView,
)

urlpatterns = [
    path(
        "operations/vendor-services/",
        VendorServiceListCreateView.as_view(),
        name="vendor-service-list",
    ),
    path(
        "operations/vendor-services/<uuid:object_id>/",
        VendorServiceDetailView.as_view(),
        name="vendor-service-detail",
    ),
    path(
        "operations/service-accounts/",
        ServiceAccountListCreateView.as_view(),
        name="service-account-list",
    ),
    path(
        "operations/service-accounts/<uuid:object_id>/",
        ServiceAccountDetailView.as_view(),
        name="service-account-detail",
    ),
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
