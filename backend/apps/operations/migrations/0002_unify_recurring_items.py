from django.db import migrations, models


SERVICE_CHOICES = [
    ("DOMAIN", "Domain"),
    ("VPS", "VPS / Server"),
    ("CLOUD", "Cloud"),
    ("HOSTING", "Hosting"),
    ("SAAS", "SaaS / Software"),
    ("API", "API / Usage Service"),
    ("STORAGE", "Storage / Backup"),
    ("EMAIL", "Email Service"),
    ("AI", "AI Service"),
    ("OTHER", "Other"),
]


def _infer_type(value):
    text = (value or "").upper()
    if "DOMAIN" in text:
        return "DOMAIN"
    if "VPS" in text or "SERVER" in text:
        return "VPS"
    if "CLOUD" in text or "AZURE" in text or "AWS" in text or "GCP" in text:
        return "CLOUD"
    if "HOST" in text:
        return "HOSTING"
    if "API" in text:
        return "API"
    if "STORAGE" in text or "BACKUP" in text:
        return "STORAGE"
    if "EMAIL" in text or "MAIL" in text:
        return "EMAIL"
    if "AI" in text or "GPT" in text or "GROQ" in text:
        return "AI"
    if "SAAS" in text or "SOFTWARE" in text:
        return "SAAS"
    return "OTHER"


def migrate_recurring_items(apps, schema_editor):
    Subscription = apps.get_model("operations", "Subscription")
    Domain = apps.get_model("operations", "Domain")
    InfrastructureAsset = apps.get_model("operations", "InfrastructureAsset")
    Vendor = apps.get_model("finance", "Vendor")
    FinancialAccount = apps.get_model("finance", "FinancialAccount")

    for sub in Subscription.objects.all():
        sub.service_type = _infer_type(f"{sub.category} {sub.name}")
        if sub.payment_account_id and not sub.payment_method:
            account = FinancialAccount.objects.filter(id=sub.payment_account_id).first()
            if account:
                label = account.institution_name or account.name
                sub.payment_method = f"{label} ••••{account.last_four}" if account.last_four else label
        sub.save(update_fields=["service_type", "payment_method"])

    for domain in Domain.objects.all():
        vendor = None
        if domain.registrar:
            vendor = Vendor.objects.filter(
                legal_entity_id=domain.legal_entity_id,
                name__iexact=domain.registrar,
            ).first()
        reference_bits = [bit for bit in [domain.registrar, f"DNS: {domain.dns_provider}" if domain.dns_provider else ""] if bit]
        existing = Subscription.objects.filter(
            legal_entity_id=domain.legal_entity_id,
            name__iexact=domain.domain_name,
        ).first()
        if existing:
            changed = []
            if existing.service_type == "OTHER":
                existing.service_type = "DOMAIN"; changed.append("service_type")
            if existing.next_renewal_date is None:
                existing.next_renewal_date = domain.expiry_date; changed.append("next_renewal_date")
            if existing.started_on is None and domain.purchase_date:
                existing.started_on = domain.purchase_date; changed.append("started_on")
            if existing.amount == 0:
                existing.amount = domain.renewal_amount; existing.currency = domain.currency
                changed += ["amount", "currency"]
            if not existing.reference and reference_bits:
                existing.reference = " · ".join(reference_bits)[:255]; changed.append("reference")
            if not existing.description and domain.purpose:
                existing.description = domain.purpose; changed.append("description")
            if not existing.notes and domain.notes:
                existing.notes = domain.notes; changed.append("notes")
            if not existing.vendor_id and vendor:
                existing.vendor_id = vendor.id; changed.append("vendor")
            if changed:
                existing.save(update_fields=list(dict.fromkeys(changed)))
        else:
            Subscription.objects.create(
                legal_entity_id=domain.legal_entity_id,
                vendor_id=vendor.id if vendor else None,
                name=domain.domain_name,
                service_type="DOMAIN",
                description=domain.purpose,
                reference=" · ".join(reference_bits)[:255],
                amount=domain.renewal_amount,
                currency=domain.currency,
                billing_cycle="ANNUAL",
                started_on=domain.purchase_date,
                next_renewal_date=domain.expiry_date,
                auto_renew=domain.auto_renew,
                status=domain.status,
                notes=domain.notes,
            )

    type_map = {
        "VPS": "VPS", "HOSTING": "HOSTING", "CLOUD": "CLOUD",
        "STORAGE": "STORAGE", "BACKUP": "STORAGE", "EMAIL": "EMAIL",
    }
    for asset in InfrastructureAsset.objects.all():
        service_type = type_map.get(asset.asset_type, "OTHER")
        existing = Subscription.objects.filter(
            legal_entity_id=asset.legal_entity_id,
            name__iexact=asset.name,
        ).first()
        if existing:
            changed = []
            if existing.service_type == "OTHER":
                existing.service_type = service_type; changed.append("service_type")
            if existing.next_renewal_date is None and asset.next_renewal_date:
                existing.next_renewal_date = asset.next_renewal_date; changed.append("next_renewal_date")
            if existing.started_on is None and asset.started_on:
                existing.started_on = asset.started_on; changed.append("started_on")
            if existing.amount == 0:
                existing.amount = asset.renewal_amount; existing.currency = asset.currency
                changed += ["amount", "currency"]
            if not existing.reference and asset.provider_reference:
                existing.reference = asset.provider_reference; changed.append("reference")
            if not existing.description and asset.purpose:
                existing.description = asset.purpose; changed.append("description")
            if not existing.notes and asset.notes:
                existing.notes = asset.notes; changed.append("notes")
            if not existing.vendor_id and asset.vendor_id:
                existing.vendor_id = asset.vendor_id; changed.append("vendor")
            if changed:
                existing.save(update_fields=list(dict.fromkeys(changed)))
        else:
            Subscription.objects.create(
                legal_entity_id=asset.legal_entity_id,
                vendor_id=asset.vendor_id,
                name=asset.name,
                service_type=service_type,
                description=asset.purpose,
                reference=asset.provider_reference,
                amount=asset.renewal_amount,
                currency=asset.currency,
                billing_cycle=asset.billing_cycle,
                started_on=asset.started_on,
                next_renewal_date=asset.next_renewal_date,
                auto_renew=asset.auto_renew,
                status=asset.status,
                notes=asset.notes,
            )


class Migration(migrations.Migration):
    dependencies = [("operations", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="service_type",
            field=models.CharField(choices=SERVICE_CHOICES, default="OTHER", max_length=20),
        ),
        migrations.AddField(
            model_name="subscription",
            name="reference",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="subscription",
            name="payment_method",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.RunPython(migrate_recurring_items, migrations.RunPython.noop),
        migrations.RemoveField(model_name="subscription", name="category"),
        migrations.RemoveField(model_name="subscription", name="product"),
        migrations.RemoveField(model_name="subscription", name="cost_center"),
        migrations.RemoveField(model_name="subscription", name="payment_account"),
        migrations.RemoveField(model_name="subscription", name="expense_account"),
        migrations.RemoveField(model_name="subscription", name="payable_account"),
    ]
