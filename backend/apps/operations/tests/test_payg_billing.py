from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from apps.accounting.models import Account, AccountType, FiscalPeriod, NormalBalance
from apps.finance.models import (
    Expense,
    FinancialAccount,
    FinancialAccountType,
    Vendor,
)
from apps.finance.services import approve_expense, pay_expense, submit_expense
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.operations.models import (
    BillingInvoiceStatus,
    BillingMode,
    ServiceAccount,
    Subscription,
    VendorService,
)


def signed_in_owner(email: str, name: str):
    owner = User.objects.create_user(email=email, password="test-pass-123")
    organization, entity, membership = create_organization_with_owner(
        owner=owner,
        name=name,
        base_currency="USD",
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session["active_legal_entity_id"] = str(entity.id)
    session.save()
    return client, owner, entity, membership


def make_payg_subscription(entity, alias="Primary"):
    vendor = Vendor.objects.create(
        legal_entity=entity,
        code=f"V{Vendor.objects.count() + 1}",
        name=f"Cloud Vendor {Vendor.objects.count() + 1}",
    )
    service = VendorService.objects.create(
        legal_entity=entity,
        vendor=vendor,
        code="CLOUD",
        name="Cloud Usage",
        service_type="CLOUD",
    )
    account = ServiceAccount.objects.create(
        legal_entity=entity,
        service=service,
        alias=alias,
    )
    subscription = Subscription.objects.create(
        legal_entity=entity,
        vendor=vendor,
        service=service,
        service_account=account,
        name=f"Cloud PAYG {alias}",
        service_type="CLOUD",
        billing_mode=BillingMode.PAYG,
        estimated_cost=Decimal("12.00"),
        monthly_budget=Decimal("20.00"),
        budget_alert_thresholds=[50, 80, 100],
        usage_unit="GB",
        amount=Decimal("0"),
        currency="USD",
    )
    return vendor, subscription


def post_json(client, path, payload):
    return client.post(path, data=payload, content_type="application/json")


def put_json(client, path, payload):
    return client.put(path, data=payload, content_type="application/json")


def patch_json(client, path, payload):
    return client.patch(path, data=payload, content_type="application/json")


def create_period(client, subscription, *, start="2026-09-01", end="2026-09-30"):
    response = post_json(
        client,
        "/api/v1/operations/billing/periods/",
        {
            "subscription": str(subscription.id),
            "period_start": start,
            "period_end": end,
            "estimated_cost": "12.00",
            "current_usage_amount": "0.00",
            "usage_unit": "GB",
        },
    )
    assert response.status_code == 201, response.content
    return response.json()


@pytest.mark.django_db
def test_payg_period_keeps_estimate_usage_actual_and_paid_separate():
    client, _, entity, _ = signed_in_owner(
        "payg-period@example.com",
        "PAYG Period Org",
    )
    _, subscription = make_payg_subscription(entity)
    period = create_period(client, subscription)

    updated = patch_json(
        client,
        f"/api/v1/operations/billing/periods/{period['id']}/",
        {
            "current_usage_amount": "18.00",
            "usage_quantity": "350.5000",
        },
    )
    assert updated.status_code == 200, updated.content
    body = updated.json()
    assert body["estimated_cost"] == "12.00"
    assert body["current_usage_amount"] == "18.00"
    assert body["actual_billed_amount"] == "0"
    assert body["paid_amount"] == "0"
    assert body["missing_invoice"] is True
    assert body["status"] == "AWAITING_INVOICE"
    assert body["budget_percent"] == "90.0"
    assert body["budget_thresholds_reached"] == [50, 80]
    assert body["over_budget"] is False

    summary = client.get("/api/v1/operations/billing/summary/")
    assert summary.status_code == 200
    data = summary.json()
    assert data["missing_invoice_count"] == 1
    assert data["over_budget_period_count"] == 0
    assert data["totals_by_currency"][0]["currency"] == "USD"
    assert data["totals_by_currency"][0]["current_usage_amount"] == "18.00"


@pytest.mark.django_db
def test_invoice_duplicate_detection_and_partial_multi_invoice_payment_allocations():
    client, _, entity, _ = signed_in_owner(
        "billing-allocation@example.com",
        "Billing Allocation Org",
    )
    vendor, subscription = make_payg_subscription(entity)
    period = create_period(client, subscription, start="2026-10-01", end="2026-10-31")

    invoice1 = post_json(
        client,
        "/api/v1/operations/billing/invoices/",
        {
            "billing_period": period["id"],
            "invoice_number": "INV-100",
            "invoice_date": "2026-10-31",
            "currency": "USD",
            "subtotal": "10.00",
            "tax_amount": "0.00",
            "total_amount": "10.00",
        },
    )
    assert invoice1.status_code == 201, invoice1.content
    invoice1 = invoice1.json()

    invoice2 = post_json(
        client,
        "/api/v1/operations/billing/invoices/",
        {
            "billing_period": period["id"],
            "invoice_number": "INV-101",
            "invoice_date": "2026-10-31",
            "currency": "USD",
            "subtotal": "5.00",
            "tax_amount": "0.00",
            "total_amount": "5.00",
        },
    )
    assert invoice2.status_code == 201, invoice2.content
    invoice2 = invoice2.json()

    duplicate = post_json(
        client,
        "/api/v1/operations/billing/invoices/",
        {
            "billing_period": period["id"],
            "vendor": str(vendor.id),
            "invoice_number": "inv-100",
            "invoice_date": "2026-10-31",
            "currency": "USD",
            "subtotal": "10.00",
            "tax_amount": "0.00",
            "total_amount": "10.00",
        },
    )
    assert duplicate.status_code == 400
    assert "already recorded" in str(duplicate.json()).lower()

    payment1 = post_json(
        client,
        "/api/v1/operations/billing/payments/",
        {
            "subscription": str(subscription.id),
            "paid_on": "2026-11-02",
            "amount": "12.00",
            "currency": "USD",
            "reference": "CARD-1",
        },
    )
    assert payment1.status_code == 201, payment1.content
    payment1 = payment1.json()

    allocated = put_json(
        client,
        f"/api/v1/operations/billing/payments/{payment1['id']}/allocations/",
        {
            "allocations": [
                {"invoice": invoice1["id"], "amount": "10.00"},
                {"invoice": invoice2["id"], "amount": "2.00"},
            ]
        },
    )
    assert allocated.status_code == 200, allocated.content
    assert allocated.json()["allocated_amount"] == "12.00"
    assert allocated.json()["unallocated_amount"] == "0.00"

    invoices = client.get("/api/v1/operations/billing/invoices/").json()
    by_number = {item["invoice_number"]: item for item in invoices}
    assert by_number["INV-100"]["status"] == BillingInvoiceStatus.PAID
    assert by_number["INV-101"]["status"] == BillingInvoiceStatus.PARTIALLY_PAID
    assert by_number["INV-101"]["paid_amount"] == "2.00"
    assert by_number["INV-101"]["outstanding_amount"] == "3.00"

    payment2 = post_json(
        client,
        "/api/v1/operations/billing/payments/",
        {
            "subscription": str(subscription.id),
            "paid_on": "2026-11-03",
            "amount": "3.00",
            "currency": "USD",
        },
    ).json()
    final_allocation = put_json(
        client,
        f"/api/v1/operations/billing/payments/{payment2['id']}/allocations/",
        {
            "allocations": [
                {"invoice": invoice2["id"], "amount": "3.00"},
            ]
        },
    )
    assert final_allocation.status_code == 200, final_allocation.content

    period_after = client.get(
        f"/api/v1/operations/billing/periods/{period['id']}/"
    ).json()
    assert period_after["actual_billed_amount"] == "15.00"
    assert period_after["paid_amount"] == "15.00"
    assert period_after["status"] == "PAID"

    over_allocate = put_json(
        client,
        f"/api/v1/operations/billing/payments/{payment2['id']}/allocations/",
        {
            "allocations": [
                {"invoice": invoice2["id"], "amount": "4.00"},
            ]
        },
    )
    assert over_allocate.status_code == 400


@pytest.mark.django_db
def test_invoice_and_payment_reconcile_to_accounting_records():
    client, owner, entity, membership = signed_in_owner(
        "billing-reconcile@example.com",
        "Billing Reconcile Org",
    )
    vendor, subscription = make_payg_subscription(entity)
    FiscalPeriod.objects.create(
        legal_entity=entity,
        name="FY 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    expense_account = Account.objects.create(
        legal_entity=entity,
        code="6100",
        name="Cloud Expense",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
    )
    payable = Account.objects.create(
        legal_entity=entity,
        code="2100",
        name="Accounts Payable",
        account_type=AccountType.LIABILITY,
        normal_balance=NormalBalance.CREDIT,
    )
    bank_ledger = Account.objects.create(
        legal_entity=entity,
        code="1000",
        name="Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
    )
    bank = FinancialAccount.objects.create(
        legal_entity=entity,
        name="Operating Bank",
        account_type=FinancialAccountType.BANK,
        currency="USD",
        ledger_account=bank_ledger,
    )
    expense = Expense.objects.create(
        legal_entity=entity,
        vendor=vendor,
        expense_date=date(2026, 10, 31),
        due_date=date(2026, 11, 15),
        description="Cloud PAYG October",
        reference="INV-200",
        amount=Decimal("15.00"),
        tax_amount=Decimal("0"),
        currency="USD",
        fx_rate=Decimal("1"),
        expense_account=expense_account,
        payable_account=payable,
        created_by=owner,
    )
    submit_expense(membership=membership, expense=expense)
    approve_expense(membership=membership, expense=expense)
    expense_payment = pay_expense(
        membership=membership,
        expense=expense,
        financial_account=bank,
        payment_date=date(2026, 11, 5),
        amount=Decimal("15.00"),
        currency="USD",
        fx_rate=Decimal("1"),
        reference="BANK-200",
    )

    period = create_period(client, subscription, start="2026-10-01", end="2026-10-31")
    invoice = post_json(
        client,
        "/api/v1/operations/billing/invoices/",
        {
            "billing_period": period["id"],
            "invoice_number": "INV-200",
            "invoice_date": "2026-10-31",
            "due_date": "2026-11-15",
            "currency": "USD",
            "subtotal": "15.00",
            "tax_amount": "0.00",
            "total_amount": "15.00",
            "expense": str(expense.id),
        },
    )
    assert invoice.status_code == 201, invoice.content
    invoice = invoice.json()
    assert invoice["expense_reconciliation_status"] == "MATCHED"
    assert invoice["expense_difference"] == "0.00"

    payment = post_json(
        client,
        "/api/v1/operations/billing/payments/",
        {
            "subscription": str(subscription.id),
            "paid_on": "2026-11-05",
            "amount": "15.00",
            "currency": "USD",
            "expense_payment": str(expense_payment.id),
            "reference": "BANK-200",
        },
    )
    assert payment.status_code == 201, payment.content
    payment = payment.json()
    assert payment["reconciliation_status"] == "MATCHED"
    assert payment["financial_account"] == str(bank.id)

    allocation = put_json(
        client,
        f"/api/v1/operations/billing/payments/{payment['id']}/allocations/",
        {"allocations": [{"invoice": invoice["id"], "amount": "15.00"}]},
    )
    assert allocation.status_code == 200, allocation.content

    refreshed = client.get(
        f"/api/v1/operations/billing/invoices/{invoice['id']}/"
    ).json()
    assert refreshed["status"] == "PAID"
    assert refreshed["outstanding_amount"] == "0.00"


@pytest.mark.django_db
def test_cross_entity_billing_links_are_rejected_and_budget_overage_surfaces():
    first, _, entity1, _ = signed_in_owner(
        "billing-first@example.com",
        "Billing First",
    )
    _, _, entity2, _ = signed_in_owner(
        "billing-second@example.com",
        "Billing Second",
    )
    _, subscription1 = make_payg_subscription(entity1, alias="First")
    _, subscription2 = make_payg_subscription(entity2, alias="Second")

    blocked = post_json(
        first,
        "/api/v1/operations/billing/periods/",
        {
            "subscription": str(subscription2.id),
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "estimated_cost": "10.00",
        },
    )
    assert blocked.status_code == 400

    period = create_period(
        first,
        subscription1,
        start="2026-10-01",
        end="2026-10-31",
    )
    over = patch_json(
        first,
        f"/api/v1/operations/billing/periods/{period['id']}/",
        {"current_usage_amount": "25.00"},
    )
    assert over.status_code == 200, over.content
    assert over.json()["over_budget"] is True
    assert over.json()["budget_percent"] == "125.0"
    assert over.json()["budget_thresholds_reached"] == [50, 80, 100]

    dashboard = first.get("/api/v1/operations/billing/summary/").json()
    assert dashboard["over_budget_period_count"] == 1
