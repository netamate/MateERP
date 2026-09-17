from decimal import Decimal

from django.db.models import Sum

from apps.accounting.models import JournalLine, JournalStatus

from .models import Budget, BudgetLine, ExpenseAllocation


def budget_line_actual(line: BudgetLine) -> Decimal:
    budget = line.budget
    has_dimension = any((line.cost_center_id, line.product_id, line.project_id))

    if has_dimension:
        allocations = ExpenseAllocation.objects.filter(
            legal_entity=budget.legal_entity,
            expense__expense_date__gte=budget.start_date,
            expense__expense_date__lte=budget.end_date,
            expense__journal_entry__status=JournalStatus.POSTED,
        )
        if line.expense_account_id:
            allocations = allocations.filter(expense__expense_account_id=line.expense_account_id)
        if line.cost_center_id:
            allocations = allocations.filter(cost_center_id=line.cost_center_id)
        if line.product_id:
            allocations = allocations.filter(product_id=line.product_id)
        if line.project_id:
            allocations = allocations.filter(project_id=line.project_id)
        return allocations.aggregate(total=Sum("base_amount"))["total"] or Decimal("0")

    if not line.expense_account_id:
        return Decimal("0")

    totals = JournalLine.objects.filter(
        journal_entry__legal_entity=budget.legal_entity,
        journal_entry__status=JournalStatus.POSTED,
        journal_entry__entry_date__gte=budget.start_date,
        journal_entry__entry_date__lte=budget.end_date,
        account_id=line.expense_account_id,
    ).aggregate(debit=Sum("base_debit"), credit=Sum("base_credit"))
    debit = totals["debit"] or Decimal("0")
    credit = totals["credit"] or Decimal("0")
    return debit - credit


def budget_actuals(budget: Budget) -> dict:
    lines = []
    total_budget = Decimal("0")
    total_actual = Decimal("0")

    for line in budget.lines.select_related(
        "expense_account",
        "cost_center",
        "product",
        "project",
    ):
        actual = budget_line_actual(line)
        variance = line.amount - actual
        utilization = Decimal("0")
        if line.amount:
            utilization = (actual / line.amount * Decimal("100")).quantize(Decimal("0.01"))
        total_budget += line.amount
        total_actual += actual
        lines.append(
            {
                "id": str(line.id),
                "expense_account_id": str(line.expense_account_id)
                if line.expense_account_id
                else None,
                "expense_account_name": line.expense_account.name if line.expense_account else None,
                "cost_center_id": str(line.cost_center_id) if line.cost_center_id else None,
                "cost_center_name": line.cost_center.name if line.cost_center else None,
                "product_id": str(line.product_id) if line.product_id else None,
                "product_name": line.product.name if line.product else None,
                "project_id": str(line.project_id) if line.project_id else None,
                "project_name": line.project.name if line.project else None,
                "budget_amount": line.amount,
                "actual_amount": actual,
                "variance": variance,
                "utilization_percent": utilization,
                "notes": line.notes,
            }
        )

    return {
        "budget_id": str(budget.id),
        "name": budget.name,
        "base_currency": budget.legal_entity.base_currency,
        "start_date": budget.start_date,
        "end_date": budget.end_date,
        "status": budget.status,
        "total_budget": total_budget,
        "total_actual": total_actual,
        "total_variance": total_budget - total_actual,
        "lines": lines,
    }
