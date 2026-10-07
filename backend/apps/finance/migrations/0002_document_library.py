import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone

import apps.finance.models


def backfill_document_library_fields(apps, schema_editor):
    FinanceDocument = apps.get_model("finance", "FinanceDocument")
    db = schema_editor.connection.alias
    for document in FinanceDocument.objects.using(db).all().iterator():
        document_date = document.created_at.date() if document.created_at else timezone.localdate()
        FinanceDocument.objects.using(db).filter(pk=document.pk).update(
            document_date=document_date,
            standardized_name=document.original_name,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0001_initial"),
        ("operations", "0004_vendor_service_accounts"),
    ]

    operations = [
        migrations.AddField(
            model_name="financedocument",
            name="document_date",
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name="financedocument",
            name="reference",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="financedocument",
            name="standardized_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="financedocument",
            name="service",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documents",
                to="operations.vendorservice",
            ),
        ),
        migrations.AddField(
            model_name="financedocument",
            name="service_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documents",
                to="operations.serviceaccount",
            ),
        ),
        migrations.AddField(
            model_name="financedocument",
            name="subscription",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documents",
                to="operations.subscription",
            ),
        ),
        migrations.RunPython(backfill_document_library_fields, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="financedocument",
            name="document_date",
            field=models.DateField(default=timezone.localdate),
        ),
        migrations.AlterField(
            model_name="financedocument",
            name="document_type",
            field=models.CharField(
                choices=[
                    ("RECEIPT", "Receipt"),
                    ("INVOICE", "Invoice"),
                    ("BILL", "Bill"),
                    ("STATEMENT", "Statement"),
                    ("PAYSLIP", "Payslip"),
                    ("PAYMENT_CONFIRMATION", "Payment confirmation"),
                    ("CREDIT_NOTE", "Credit note"),
                    ("OTHER", "Other"),
                ],
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="financedocument",
            name="file",
            field=models.FileField(upload_to=apps.finance.models.finance_document_upload_path),
        ),
        migrations.AlterModelOptions(
            name="financedocument",
            options={"ordering": ["-document_date", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="financedocument",
            index=models.Index(
                fields=["legal_entity", "document_date"],
                name="finance_doc_date_idx",
            ),
        ),
    ]
