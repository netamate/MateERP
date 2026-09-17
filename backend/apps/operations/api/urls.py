from django.urls import path

from .views import (
    DomainDetailView,
    DomainListCreateView,
    DomainRenewalHistoryView,
    DomainRenewView,
    InfrastructureAssetDetailView,
    InfrastructureAssetListCreateView,
    RenewalCalendarView,
    SubscriptionDetailView,
    SubscriptionListCreateView,
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
    path("operations/domains/", DomainListCreateView.as_view(), name="domain-list"),
    path(
        "operations/domains/<uuid:object_id>/",
        DomainDetailView.as_view(),
        name="domain-detail",
    ),
    path(
        "operations/domains/<uuid:domain_id>/renew/",
        DomainRenewView.as_view(),
        name="domain-renew",
    ),
    path(
        "operations/domains/<uuid:domain_id>/renewals/",
        DomainRenewalHistoryView.as_view(),
        name="domain-renewal-history",
    ),
    path(
        "operations/infrastructure/",
        InfrastructureAssetListCreateView.as_view(),
        name="infrastructure-list",
    ),
    path(
        "operations/infrastructure/<uuid:object_id>/",
        InfrastructureAssetDetailView.as_view(),
        name="infrastructure-detail",
    ),
    path("operations/renewals/", RenewalCalendarView.as_view(), name="renewal-calendar"),
]
