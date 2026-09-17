from django.urls import path

from .views import (
    BudgetActualView,
    BudgetDetailView,
    BudgetLineListCreateView,
    BudgetListCreateView,
    CostCenterDetailView,
    CostCenterListCreateView,
    ExpenseAllocationView,
    ProductDetailView,
    ProductListCreateView,
    ProjectDetailView,
    ProjectListCreateView,
)

urlpatterns = [
    path("planning/cost-centers/", CostCenterListCreateView.as_view(), name="cost-center-list"),
    path(
        "planning/cost-centers/<uuid:object_id>/",
        CostCenterDetailView.as_view(),
        name="cost-center-detail",
    ),
    path("planning/products/", ProductListCreateView.as_view(), name="product-list"),
    path(
        "planning/products/<uuid:object_id>/",
        ProductDetailView.as_view(),
        name="product-detail",
    ),
    path("planning/projects/", ProjectListCreateView.as_view(), name="project-list"),
    path(
        "planning/projects/<uuid:object_id>/",
        ProjectDetailView.as_view(),
        name="project-detail",
    ),
    path(
        "planning/expenses/<uuid:expense_id>/allocations/",
        ExpenseAllocationView.as_view(),
        name="expense-allocation-list",
    ),
    path("planning/budgets/", BudgetListCreateView.as_view(), name="budget-list"),
    path(
        "planning/budgets/<uuid:budget_id>/",
        BudgetDetailView.as_view(),
        name="budget-detail",
    ),
    path(
        "planning/budgets/<uuid:budget_id>/lines/",
        BudgetLineListCreateView.as_view(),
        name="budget-line-list",
    ),
    path(
        "planning/budgets/<uuid:budget_id>/actuals/",
        BudgetActualView.as_view(),
        name="budget-actuals",
    ),
]
