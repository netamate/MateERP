from django.urls import path

from .views import (
    ReconciliationCandidateView,
    ReconciliationCompleteView,
    ReconciliationDetailView,
    ReconciliationItemsView,
    ReconciliationListCreateView,
)

urlpatterns = [
    path(
        "finance/reconciliations/",
        ReconciliationListCreateView.as_view(),
        name="reconciliation-list",
    ),
    path(
        "finance/reconciliations/<uuid:reconciliation_id>/",
        ReconciliationDetailView.as_view(),
        name="reconciliation-detail",
    ),
    path(
        "finance/reconciliations/<uuid:reconciliation_id>/candidates/",
        ReconciliationCandidateView.as_view(),
        name="reconciliation-candidates",
    ),
    path(
        "finance/reconciliations/<uuid:reconciliation_id>/items/",
        ReconciliationItemsView.as_view(),
        name="reconciliation-items",
    ),
    path(
        "finance/reconciliations/<uuid:reconciliation_id>/complete/",
        ReconciliationCompleteView.as_view(),
        name="reconciliation-complete",
    ),
]
