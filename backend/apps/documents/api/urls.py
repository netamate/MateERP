from django.urls import path

from .views import FinanceDocumentListCreateView

urlpatterns = [
    path("finance/documents/", FinanceDocumentListCreateView.as_view(), name="finance-documents"),
]
