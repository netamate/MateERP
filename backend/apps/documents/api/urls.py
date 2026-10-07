from django.urls import path

from .views import (
    FinanceDocumentContentView,
    FinanceDocumentDetailView,
    FinanceDocumentListCreateView,
)

urlpatterns = [
    path(
        "finance/documents/",
        FinanceDocumentListCreateView.as_view(),
        name="finance-documents",
    ),
    path(
        "finance/documents/<uuid:object_id>/",
        FinanceDocumentDetailView.as_view(),
        name="finance-document-detail",
    ),
    path(
        "finance/documents/<uuid:object_id>/content/",
        FinanceDocumentContentView.as_view(),
        name="finance-document-content",
    ),
]
