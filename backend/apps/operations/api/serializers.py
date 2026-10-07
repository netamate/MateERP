from decimal import Decimal

from rest_framework import serializers

from ..models import (
    BillingPayment,
    BillingPaymentAllocation,
    ServiceAccount,
    Subscription,
    SubscriptionBillingPeriod,
    SubscriptionInvoice,
    SubscriptionPayment,
    VendorService,
)
from ..selectors import billing_period_snapshot, invoice_paid_amount


class VendorServiceSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    account_count = serializers.IntegerField(source="accounts.count", read_only=True)

    class Meta:
        model = VendorService
        exclude = ["legal_entity"]
        read_only_fields = ["id", "vendor_name", "account_count", "created_at", "updated_at"]

    def validate(self, attrs):
        entity = self.context.get("legal_entity")
        vendor = attrs.get("vendor", getattr(self.instance, "vendor", None))
        code = attrs.get("code", getattr(self.instance, "code", "")).strip().upper()
        if not vendor or not entity or vendor.legal_entity_id != entity.id:
            raise serializers.ValidationError(
                {"vendor": "Choose a vendor from the active legal entity."}
            )
        if not self.instance and vendor.status != "ACTIVE":
            raise serializers.ValidationError(
                {"vendor": "Archived vendor cannot accept a new service."}
            )
        if self.instance and vendor.pk != self.instance.vendor_id:
            raise serializers.ValidationError(
                {
                    "vendor": (
                        "To preserve subscription history, a service cannot move to another vendor."
                    )
                }
            )
        next_type = attrs.get("service_type", getattr(self.instance, "service_type", "OTHER"))
        if (
            self.instance
            and next_type != self.instance.service_type
            and self.instance.subscriptions.exists()
        ):
            raise serializers.ValidationError(
                {"service_type": "Category cannot change while subscriptions are linked."}
            )
        if not code:
            raise serializers.ValidationError({"code": "Service code is required."})
        others = VendorService.objects.filter(legal_entity=entity, vendor=vendor, code__iexact=code)
        if self.instance:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise serializers.ValidationError(
                {"code": "This vendor already has that service code."}
            )
        attrs["code"] = code
        return attrs


class ServiceAccountSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    vendor_id = serializers.UUIDField(source="service.vendor_id", read_only=True)
    vendor_name = serializers.CharField(source="service.vendor.name", read_only=True)
    subscription_count = serializers.IntegerField(source="subscriptions.count", read_only=True)

    class Meta:
        model = ServiceAccount
        exclude = ["legal_entity"]
        read_only_fields = [
            "id",
            "code",
            "service_name",
            "vendor_id",
            "vendor_name",
            "subscription_count",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        entity = self.context.get("legal_entity")
        service = attrs.get("service", getattr(self.instance, "service", None))
        alias = attrs.get("alias", getattr(self.instance, "alias", "")).strip()
        if not service or not entity or service.legal_entity_id != entity.id:
            raise serializers.ValidationError(
                {"service": "Choose a service from the active legal entity."}
            )
        if not self.instance and service.status != "ACTIVE":
            raise serializers.ValidationError(
                {"service": "Archived service cannot accept a new account."}
            )
        if self.instance and service.pk != self.instance.service_id:
            raise serializers.ValidationError(
                {
                    "service": (
                        "To preserve subscription history, an account cannot move "
                        "to another service."
                    )
                }
            )
        if not alias:
            raise serializers.ValidationError({"alias": "Account alias is required."})
        existing = ServiceAccount.objects.filter(service=service, alias__iexact=alias)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(
                {"alias": "An account with this alias already exists for the service."}
            )
        attrs["alias"] = alias
        return attrs


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = SubscriptionPayment
        exclude = ["legal_entity", "created_by"]
        read_only_fields = ["id", "created_at", "created_by_email"]


class SubscriptionSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    vendor_service_name = serializers.CharField(source="service.name", read_only=True)
    account_alias = serializers.CharField(source="service_account.alias", read_only=True)
    account_code = serializers.CharField(source="service_account.code", read_only=True)
    payments = SubscriptionPaymentSerializer(many=True, read_only=True)
    payment_count = serializers.IntegerField(source="payments.count", read_only=True)

    class Meta:
        model = Subscription
        exclude = ["legal_entity"]
        read_only_fields = [
            "id",
            "subscription_code",
            "created_at",
            "updated_at",
            "vendor_name",
            "vendor_service_name",
            "account_alias",
            "account_code",
            "payments",
            "payment_count",
            "reminder_email",
            "reminder_email_recipients",
        ]

    def validate(self, attrs):
        entity = self.context.get("legal_entity")
        vendor = attrs.get("vendor", getattr(self.instance, "vendor", None))
        service = attrs.get("service", getattr(self.instance, "service", None))
        account = attrs.get("service_account", getattr(self.instance, "service_account", None))
        if entity:
            for field, obj in (
                ("vendor", vendor),
                ("service", service),
                ("service_account", account),
            ):
                if obj and obj.legal_entity_id != entity.id:
                    raise serializers.ValidationError(
                        {field: "This record does not belong to the active legal entity."}
                    )
        if service and vendor and service.vendor_id != vendor.pk:
            raise serializers.ValidationError({"service": "Service must belong to this vendor."})
        if (
            service
            and service.status != "ACTIVE"
            and (not self.instance or self.instance.service_id != service.pk)
        ):
            raise serializers.ValidationError({"service": "Archived services cannot be assigned."})
        if (
            account
            and account.status != "ACTIVE"
            and (not self.instance or self.instance.service_account_id != account.pk)
        ):
            raise serializers.ValidationError(
                {"service_account": "Archived accounts cannot be assigned."}
            )
        if account and not service:
            raise serializers.ValidationError({"service_account": "Select a service first."})
        if account and account.service_id != service.pk:
            raise serializers.ValidationError(
                {"service_account": "Account must belong to the selected service."}
            )
        return attrs

    def validate_budget_alert_thresholds(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Budget alert thresholds must be a list.")
        normalized = []
        for item in value:
            if not isinstance(item, int) or isinstance(item, bool) or item < 1 or item > 500:
                raise serializers.ValidationError(
                    "Budget alert thresholds must be integer percentages between 1 and 500."
                )
            if item not in normalized:
                normalized.append(item)
        return sorted(normalized)

    def validate_monthly_budget(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Monthly budget must be greater than zero.")
        return value

    def validate_reminder_days(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Reminder days must be a list.")
        normalized = []
        for item in value:
            if not isinstance(item, int) or isinstance(item, bool) or item < 0 or item > 365:
                raise serializers.ValidationError(
                    "Reminder day offsets must be integers between 0 and 365."
                )
            if item not in normalized:
                normalized.append(item)
        return sorted(normalized, reverse=True)

    def validate_reminder_email_recipients(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Email recipients must be a list.")
        field = serializers.EmailField()
        normalized = []
        for item in value:
            email = field.run_validation(item)
            if email not in normalized:
                normalized.append(email)
        return normalized


class SubscriptionPaymentActionSerializer(serializers.Serializer):
    paid_on = serializers.DateField()
    amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
    )
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True)


class RenewalQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError("end_date cannot be before start_date.")
        return attrs


class SubscriptionBillingPeriodSerializer(serializers.ModelSerializer):
    subscription_name = serializers.CharField(source="subscription.name", read_only=True)
    subscription_code = serializers.CharField(
        source="subscription.subscription_code",
        read_only=True,
    )
    vendor_name = serializers.CharField(source="subscription.vendor.name", read_only=True)
    service_name = serializers.CharField(source="subscription.service.name", read_only=True)
    account_alias = serializers.CharField(
        source="subscription.service_account.alias",
        read_only=True,
    )
    billing_mode = serializers.CharField(source="subscription.billing_mode", read_only=True)
    currency = serializers.CharField(source="subscription.currency", read_only=True)
    status = serializers.SerializerMethodField()
    actual_billed_amount = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    outstanding_amount = serializers.SerializerMethodField()
    variance_from_estimate = serializers.SerializerMethodField()
    monthly_budget = serializers.SerializerMethodField()
    budget_percent = serializers.SerializerMethodField()
    budget_thresholds_reached = serializers.SerializerMethodField()
    over_budget = serializers.SerializerMethodField()
    missing_invoice = serializers.SerializerMethodField()
    invoice_count = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionBillingPeriod
        exclude = ["legal_entity", "created_by"]
        read_only_fields = [
            "id",
            "current_usage_updated_at",
            "created_at",
            "updated_at",
            "subscription_name",
            "subscription_code",
            "vendor_name",
            "service_name",
            "account_alias",
            "billing_mode",
            "currency",
            "status",
            "actual_billed_amount",
            "paid_amount",
            "outstanding_amount",
            "variance_from_estimate",
            "monthly_budget",
            "budget_percent",
            "budget_thresholds_reached",
            "over_budget",
            "missing_invoice",
            "invoice_count",
        ]

    def _snapshot(self, obj):
        cache_name = "_billing_snapshot_cache"
        if not hasattr(obj, cache_name):
            setattr(obj, cache_name, billing_period_snapshot(obj))
        return getattr(obj, cache_name)

    def get_status(self, obj):
        return self._snapshot(obj)["status"]

    def get_actual_billed_amount(self, obj):
        return str(self._snapshot(obj)["actual_billed_amount"])

    def get_paid_amount(self, obj):
        return str(self._snapshot(obj)["paid_amount"])

    def get_outstanding_amount(self, obj):
        return str(self._snapshot(obj)["outstanding_amount"])

    def get_variance_from_estimate(self, obj):
        return str(self._snapshot(obj)["variance_from_estimate"])

    def get_monthly_budget(self, obj):
        value = self._snapshot(obj)["monthly_budget"]
        return str(value) if value is not None else None

    def get_budget_percent(self, obj):
        value = self._snapshot(obj)["budget_percent"]
        return str(value) if value is not None else None

    def get_budget_thresholds_reached(self, obj):
        return self._snapshot(obj)["budget_thresholds_reached"]

    def get_over_budget(self, obj):
        return self._snapshot(obj)["over_budget"]

    def get_missing_invoice(self, obj):
        return self._snapshot(obj)["missing_invoice"]

    def get_invoice_count(self, obj):
        return self._snapshot(obj)["invoice_count"]

    def validate(self, attrs):
        entity = self.context.get("legal_entity")
        subscription = attrs.get(
            "subscription",
            getattr(self.instance, "subscription", None),
        )
        if not subscription or not entity or subscription.legal_entity_id != entity.id:
            raise serializers.ValidationError(
                {"subscription": "Choose a subscription from the active legal entity."}
            )
        start = attrs.get("period_start", getattr(self.instance, "period_start", None))
        end = attrs.get("period_end", getattr(self.instance, "period_end", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"period_end": "Billing period end cannot be before the start date."}
            )
        for field in ("estimated_cost", "current_usage_amount"):
            value = attrs.get(field, getattr(self.instance, field, Decimal("0")))
            if value is not None and value < 0:
                raise serializers.ValidationError({field: "Billing values cannot be negative."})
        quantity = attrs.get(
            "usage_quantity",
            getattr(self.instance, "usage_quantity", None),
        )
        if quantity is not None and quantity < 0:
            raise serializers.ValidationError(
                {"usage_quantity": "Usage quantity cannot be negative."}
            )
        return attrs


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    subscription = serializers.UUIDField(
        source="billing_period.subscription_id",
        read_only=True,
    )
    subscription_name = serializers.CharField(
        source="billing_period.subscription.name",
        read_only=True,
    )
    subscription_code = serializers.CharField(
        source="billing_period.subscription.subscription_code",
        read_only=True,
    )
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    period_start = serializers.DateField(
        source="billing_period.period_start",
        read_only=True,
    )
    period_end = serializers.DateField(
        source="billing_period.period_end",
        read_only=True,
    )
    document_name = serializers.CharField(
        source="document.standardized_name",
        read_only=True,
    )
    expense_description = serializers.CharField(
        source="expense.description",
        read_only=True,
    )
    paid_amount = serializers.SerializerMethodField()
    outstanding_amount = serializers.SerializerMethodField()
    expense_reconciliation_status = serializers.SerializerMethodField()
    expense_difference = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionInvoice
        exclude = ["legal_entity", "created_by"]
        extra_kwargs = {"vendor": {"required": False}}
        read_only_fields = [
            "id",
            "status",
            "created_at",
            "updated_at",
            "subscription",
            "subscription_name",
            "subscription_code",
            "vendor_name",
            "period_start",
            "period_end",
            "document_name",
            "expense_description",
            "paid_amount",
            "outstanding_amount",
            "expense_reconciliation_status",
            "expense_difference",
        ]

    def get_paid_amount(self, obj):
        return str(invoice_paid_amount(obj))

    def get_outstanding_amount(self, obj):
        return str(max(obj.total_amount - invoice_paid_amount(obj), Decimal("0")))

    def get_expense_reconciliation_status(self, obj):
        if not obj.expense_id:
            return "UNMATCHED"
        if obj.expense.currency != obj.currency or obj.expense.amount != obj.total_amount:
            return "MISMATCH"
        return "MATCHED"

    def get_expense_difference(self, obj):
        if not obj.expense_id or obj.expense.currency != obj.currency:
            return None
        return str(obj.expense.amount - obj.total_amount)

    def validate(self, attrs):
        entity = self.context.get("legal_entity")
        period = attrs.get(
            "billing_period",
            getattr(self.instance, "billing_period", None),
        )
        vendor = attrs.get("vendor", getattr(self.instance, "vendor", None))
        document = attrs.get("document", getattr(self.instance, "document", None))
        expense = attrs.get("expense", getattr(self.instance, "expense", None))
        if not period or not entity or period.legal_entity_id != entity.id:
            raise serializers.ValidationError(
                {"billing_period": "Choose a billing period from the active legal entity."}
            )
        if vendor and vendor.legal_entity_id != entity.id:
            raise serializers.ValidationError({"vendor": "Vendor belongs to another legal entity."})
        if document and document.legal_entity_id != entity.id:
            raise serializers.ValidationError(
                {"document": "Document belongs to another legal entity."}
            )
        if expense and expense.legal_entity_id != entity.id:
            raise serializers.ValidationError(
                {"expense": "Expense belongs to another legal entity."}
            )
        if document:
            if document.document_type != "INVOICE":
                raise serializers.ValidationError(
                    {"document": "Linked finance document must be an invoice."}
                )
            duplicate_document = SubscriptionInvoice.objects.filter(document=document)
            if self.instance:
                duplicate_document = duplicate_document.exclude(pk=self.instance.pk)
            if duplicate_document.exists():
                raise serializers.ValidationError(
                    {"document": "This invoice document is already linked."}
                )
        if expense:
            duplicate_expense = SubscriptionInvoice.objects.filter(expense=expense)
            if self.instance:
                duplicate_expense = duplicate_expense.exclude(pk=self.instance.pk)
            if duplicate_expense.exists():
                raise serializers.ValidationError(
                    {"expense": "This accounting expense is already linked to another invoice."}
                )

        selected_vendor = vendor or period.subscription.vendor
        if selected_vendor is None:
            raise serializers.ValidationError({"vendor": "Invoice vendor is required."})
        if period.subscription.vendor_id and period.subscription.vendor_id != selected_vendor.id:
            raise serializers.ValidationError(
                {"vendor": "Invoice vendor must match the subscription vendor."}
            )
        if expense and expense.vendor_id and expense.vendor_id != selected_vendor.id:
            raise serializers.ValidationError(
                {"expense": "Expense vendor must match the invoice vendor."}
            )

        number = attrs.get(
            "invoice_number",
            getattr(self.instance, "invoice_number", ""),
        ).strip()
        duplicates = SubscriptionInvoice.objects.filter(
            vendor=selected_vendor,
            invoice_number__iexact=number,
        )
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if number and duplicates.exists():
            raise serializers.ValidationError(
                {"invoice_number": "This vendor invoice number is already recorded."}
            )

        invoice_date = attrs.get(
            "invoice_date",
            getattr(self.instance, "invoice_date", None),
        )
        due_date = attrs.get("due_date", getattr(self.instance, "due_date", None))
        if invoice_date and due_date and due_date < invoice_date:
            raise serializers.ValidationError(
                {"due_date": "Due date cannot be before the invoice date."}
            )
        subtotal = attrs.get("subtotal", getattr(self.instance, "subtotal", Decimal("0")))
        tax = attrs.get("tax_amount", getattr(self.instance, "tax_amount", Decimal("0")))
        total = attrs.get(
            "total_amount",
            getattr(self.instance, "total_amount", Decimal("0")),
        )
        if subtotal < 0 or tax < 0 or total <= 0 or subtotal + tax != total:
            raise serializers.ValidationError(
                {"total_amount": "Total must equal subtotal plus tax and be positive."}
            )
        currency = attrs.get(
            "currency",
            getattr(self.instance, "currency", ""),
        ).upper()
        if currency != period.subscription.currency:
            raise serializers.ValidationError(
                {"currency": "Invoice currency must match the subscription currency."}
            )
        attrs["invoice_number"] = number
        attrs["currency"] = currency
        if not vendor:
            attrs["vendor"] = selected_vendor
        return attrs


class BillingPaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = BillingPaymentAllocation
        fields = ["id", "invoice", "invoice_number", "amount", "created_at"]
        read_only_fields = ["id", "invoice_number", "created_at"]


class BillingPaymentSerializer(serializers.ModelSerializer):
    subscription_name = serializers.CharField(source="subscription.name", read_only=True)
    subscription_code = serializers.CharField(
        source="subscription.subscription_code",
        read_only=True,
    )
    financial_account_name = serializers.CharField(
        source="financial_account.name",
        read_only=True,
    )
    expense_payment_reference = serializers.CharField(
        source="expense_payment.reference",
        read_only=True,
    )
    allocations = BillingPaymentAllocationSerializer(many=True, read_only=True)
    allocated_amount = serializers.SerializerMethodField()
    unallocated_amount = serializers.SerializerMethodField()
    reconciliation_status = serializers.SerializerMethodField()

    class Meta:
        model = BillingPayment
        exclude = ["legal_entity", "created_by"]
        read_only_fields = [
            "id",
            "payment_code",
            "created_at",
            "subscription_name",
            "subscription_code",
            "financial_account_name",
            "expense_payment_reference",
            "allocations",
            "allocated_amount",
            "unallocated_amount",
            "reconciliation_status",
        ]

    def get_allocated_amount(self, obj):
        amount = sum(
            (allocation.amount for allocation in obj.allocations.all()),
            Decimal("0"),
        )
        return str(amount)

    def get_unallocated_amount(self, obj):
        allocated = sum(
            (allocation.amount for allocation in obj.allocations.all()),
            Decimal("0"),
        )
        return str(obj.amount - allocated)

    def get_reconciliation_status(self, obj):
        if obj.expense_payment_id:
            return "MATCHED"
        if obj.financial_account_id:
            return "ACCOUNT_IDENTIFIED"
        return "UNMATCHED"

    def validate(self, attrs):
        entity = self.context.get("legal_entity")
        subscription = attrs.get(
            "subscription",
            getattr(self.instance, "subscription", None),
        )
        financial_account = attrs.get(
            "financial_account",
            getattr(self.instance, "financial_account", None),
        )
        expense_payment = attrs.get(
            "expense_payment",
            getattr(self.instance, "expense_payment", None),
        )
        if not subscription or not entity or subscription.legal_entity_id != entity.id:
            raise serializers.ValidationError(
                {"subscription": "Choose a subscription from the active legal entity."}
            )
        for field, record in (
            ("financial_account", financial_account),
            ("expense_payment", expense_payment),
        ):
            if record and record.legal_entity_id != entity.id:
                raise serializers.ValidationError(
                    {field: "This record belongs to another legal entity."}
                )
        amount = attrs.get("amount", getattr(self.instance, "amount", Decimal("0")))
        if amount <= 0:
            raise serializers.ValidationError(
                {"amount": "Payment amount must be greater than zero."}
            )
        currency = attrs.get(
            "currency",
            getattr(self.instance, "currency", ""),
        ).upper()
        if currency != subscription.currency:
            raise serializers.ValidationError(
                {"currency": "Payment currency must match the subscription currency."}
            )
        if financial_account and financial_account.currency != currency:
            raise serializers.ValidationError(
                {"financial_account": "Financial account currency must match payment currency."}
            )
        if expense_payment:
            duplicate_payment = BillingPayment.objects.filter(expense_payment=expense_payment)
            if self.instance:
                duplicate_payment = duplicate_payment.exclude(pk=self.instance.pk)
            if duplicate_payment.exists():
                raise serializers.ValidationError(
                    {"expense_payment": "This accounting payment is already linked."}
                )
            if expense_payment.amount != amount or expense_payment.currency != currency:
                raise serializers.ValidationError(
                    {
                        "expense_payment": (
                            "Expense payment amount and currency must match this payment."
                        )
                    }
                )
            if financial_account and expense_payment.financial_account_id != financial_account.id:
                raise serializers.ValidationError(
                    {
                        "expense_payment": (
                            "Expense payment must use the selected financial account."
                        )
                    }
                )
            if not financial_account:
                attrs["financial_account"] = expense_payment.financial_account
        attrs["currency"] = currency
        return attrs


class BillingAllocationItemSerializer(serializers.Serializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=SubscriptionInvoice.objects.all())
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)


class BillingAllocationsSerializer(serializers.Serializer):
    allocations = BillingAllocationItemSerializer(many=True, allow_empty=True)

    def validate_allocations(self, value):
        seen = set()
        total = Decimal("0")
        for item in value:
            if item["invoice"].id in seen:
                raise serializers.ValidationError("Each invoice can appear only once.")
            if item["amount"] <= 0:
                raise serializers.ValidationError("Allocation amounts must be greater than zero.")
            seen.add(item["invoice"].id)
            total += item["amount"]
        return value
