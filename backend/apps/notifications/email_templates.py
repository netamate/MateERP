# ruff: noqa: E501
import html
import re
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    EmailTemplate,
    EmailTemplateStatus,
    EmailTemplateVersion,
    NotificationKind,
)

TOKEN_RE = re.compile(r"{{\s*([A-Za-z][A-Za-z0-9_]*)\s*}}")

COMMON_VARIABLES = {
    "organization_name": "Organization name",
    "legal_entity_name": "Legal entity name",
    "recipient_name": "Recipient display name",
    "recipient_email": "Recipient email address",
    "current_date": "Current date",
    "alert_title": "Alert title",
    "alert_message": "Alert message",
    "severity": "Alert severity",
    "relevant_date": "Relevant date",
    "action_url": "MateERP action URL",
}

SIGNAL_VARIABLES = {
    NotificationKind.RENEWAL_DUE: {
        "subscription_name": "Subscription name",
        "subscription_code": "Subscription permanent code",
        "vendor_name": "Vendor name",
        "days_remaining": "Days remaining",
        "amount": "Renewal amount or PAYG estimate",
        "currency": "Currency",
        "due_date": "Renewal due date",
        "payment_method": "Configured payment method",
    },
    NotificationKind.BUDGET_THRESHOLD: {
        "subscription_name": "Subscription name",
        "subscription_code": "Subscription permanent code",
        "threshold_percent": "Triggered threshold percentage",
        "budget_percent": "Current budget utilization",
        "budget": "Monthly budget",
        "tracked_cost": "Current tracked cost",
        "currency": "Currency",
    },
    NotificationKind.MISSING_INVOICE: {
        "subscription_name": "Subscription name",
        "subscription_code": "Subscription permanent code",
        "period_start": "Billing period start",
        "period_end": "Billing period end",
        "vendor_name": "Vendor name",
    },
    NotificationKind.INVOICE_OVERDUE: {
        "subscription_name": "Subscription name",
        "subscription_code": "Subscription permanent code",
        "invoice_number": "Vendor invoice number",
        "vendor_name": "Vendor name",
        "outstanding": "Outstanding amount",
        "currency": "Currency",
        "overdue_days": "Days overdue",
    },
    NotificationKind.RECONCILIATION_NEEDED: {
        "subscription_name": "Subscription name",
        "subscription_code": "Subscription permanent code",
        "invoice_number": "Invoice number when applicable",
        "payment_code": "Payment code when applicable",
        "reason": "Reconciliation reason",
        "amount": "Amount",
        "currency": "Currency",
    },
}

ALLOWED_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}
VOID_TAGS = {"br", "hr", "img"}
ALLOWED_ATTRIBUTES = {
    "*": {"style", "align"},
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "width", "height", "title"},
    "table": {"width", "cellpadding", "cellspacing", "role"},
    "td": {"width", "colspan", "rowspan", "valign"},
    "th": {"width", "colspan", "rowspan", "valign"},
}
SAFE_PROTOCOLS = {"http", "https", "mailto"}

DEFAULT_EMAIL_TEMPLATES = (
    {
        "template_key": "alert-renewal-due",
        "name": "Subscription Renewal Alert",
        "signal": NotificationKind.RENEWAL_DUE,
        "description": "Default email for upcoming subscription renewals.",
    },
    {
        "template_key": "alert-budget-threshold",
        "name": "PAYG Budget Threshold",
        "signal": NotificationKind.BUDGET_THRESHOLD,
        "description": "Default email for PAYG budget threshold alerts.",
    },
    {
        "template_key": "alert-missing-invoice",
        "name": "Missing Vendor Invoice",
        "signal": NotificationKind.MISSING_INVOICE,
        "description": "Default email when a billing period ends without an invoice.",
    },
    {
        "template_key": "alert-invoice-overdue",
        "name": "Overdue Vendor Invoice",
        "signal": NotificationKind.INVOICE_OVERDUE,
        "description": "Default email for overdue vendor invoices.",
    },
    {
        "template_key": "alert-reconciliation-needed",
        "name": "Billing Reconciliation Needed",
        "signal": NotificationKind.RECONCILIATION_NEEDED,
        "description": "Default email when invoice or payment reconciliation needs attention.",
    },
    {
        "template_key": "general-business-update",
        "name": "General Business Update",
        "signal": None,
        "description": "Reusable general-purpose template for direct email notifications.",
    },
)

BASE_HTML = """<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,sans-serif;color:#182230">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:28px 12px">
      <tr>
        <td align="center">
          <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;background:#ffffff;border:1px solid #dfe4ea">
            <tr>
              <td style="padding:24px 28px;border-bottom:3px solid #1b4db1">
                <div style="font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:#667085">{{organization_name}}</div>
                <h1 style="margin:8px 0 0;font-size:22px;line-height:1.35;color:#101828">{{alert_title}}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;font-size:14px;line-height:1.7;color:#344054">
                <p style="margin:0 0 18px">{{alert_message}}</p>
                <p style="margin:0">
                  <a href="{{action_url}}" style="display:inline-block;background:#1b4db1;color:#ffffff;text-decoration:none;padding:11px 16px;font-weight:700">Open in MateERP</a>
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 28px;border-top:1px solid #eaecf0;font-size:11px;line-height:1.6;color:#667085">
                {{legal_entity_name}} · {{severity}} · {{relevant_date}}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""

GENERAL_HTML = """<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,sans-serif;color:#182230">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:28px 12px">
      <tr><td align="center">
        <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;background:#ffffff;border:1px solid #dfe4ea">
          <tr><td style="padding:24px 28px;border-bottom:3px solid #1b4db1">
            <div style="font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:#667085">{{organization_name}}</div>
            <h1 style="margin:8px 0 0;font-size:22px;color:#101828">Business Update</h1>
          </td></tr>
          <tr><td style="padding:28px;font-size:14px;line-height:1.7;color:#344054">{{alert_message}}</td></tr>
          <tr><td style="padding:16px 28px;border-top:1px solid #eaecf0;font-size:11px;color:#667085">{{legal_entity_name}}</td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


class EmailHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "iframe", "object", "embed", "form", "input", "button", "svg"}:
            self.suppressed_depth += 1
            return
        if self.suppressed_depth or tag not in ALLOWED_TAGS:
            return
        allowed = set(ALLOWED_ATTRIBUTES.get("*", set())) | set(ALLOWED_ATTRIBUTES.get(tag, set()))
        cleaned = []
        for name, value in attrs:
            name = name.lower()
            value = value or ""
            if name not in allowed:
                continue
            if name in {"href", "src"} and not _safe_url(value):
                continue
            if name == "style":
                value = _safe_style(value)
                if not value:
                    continue
            if name == "target" and value not in {"_blank", "_self"}:
                continue
            cleaned.append(f' {name}="{html.escape(value, quote=True)}"')
        self.parts.append(f"<{tag}{''.join(cleaned)}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "iframe", "object", "embed", "form", "input", "button", "svg"}:
            if self.suppressed_depth:
                self.suppressed_depth -= 1
            return
        if self.suppressed_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.suppressed_depth:
            self.parts.append(html.escape(data, quote=False))

    def handle_entityref(self, name):
        if not self.suppressed_depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if not self.suppressed_depth:
            self.parts.append(f"&#{name};")


def _safe_url(value: str) -> bool:
    value = value.strip()
    if value.startswith(("#", "/")):
        return True
    parsed = urlparse(value)
    return parsed.scheme.lower() in SAFE_PROTOCOLS


def _safe_style(value: str) -> str:
    lower = value.lower()
    blocked = ("url(", "expression(", "javascript:", "@import", "behavior:")
    if any(item in lower for item in blocked):
        return ""
    return value[:2000]


def sanitize_email_html(value: str) -> str:
    parser = EmailHTMLSanitizer()
    parser.feed(value or "")
    parser.close()
    return "".join(parser.parts)


def variable_catalog(signal=None) -> dict[str, str]:
    result = dict(COMMON_VARIABLES)
    if signal in SIGNAL_VARIABLES:
        result.update(SIGNAL_VARIABLES[signal])
    return result


def template_variables(*parts: str) -> set[str]:
    found = set()
    for part in parts:
        found.update(TOKEN_RE.findall(part or ""))
    return found


def validate_template_variables(*, signal, subject: str, text_body: str, html_body: str) -> None:
    allowed = set(variable_catalog(signal))
    used = template_variables(subject, text_body, html_body)
    unknown = sorted(used - allowed)
    if unknown:
        raise ValidationError(
            "Unknown template variables: " + ", ".join(f"{{{{{item}}}}}" for item in unknown)
        )


def _render_tokens(value: str, context: dict, *, escape_values: bool) -> str:
    def replace(match):
        key = match.group(1)
        raw = context.get(key, "")
        text = "" if raw is None else str(raw)
        return html.escape(text, quote=True) if escape_values else text

    return TOKEN_RE.sub(replace, value or "")


def render_email_content(
    *,
    signal,
    subject_template: str,
    text_body_template: str,
    html_body_template: str,
    context: dict,
) -> dict:
    validate_template_variables(
        signal=signal,
        subject=subject_template,
        text_body=text_body_template,
        html_body=html_body_template,
    )
    subject = _render_tokens(subject_template, context, escape_values=False).strip()
    text_body = _render_tokens(text_body_template, context, escape_values=False)
    rendered_html = _render_tokens(html_body_template, context, escape_values=True)
    if not rendered_html.strip():
        paragraphs = "".join(
            f"<p>{html.escape(line)}</p>" for line in text_body.splitlines() if line.strip()
        )
        rendered_html = f"<div>{paragraphs}</div>"
    return {
        "subject": subject[:255],
        "text_body": text_body,
        "html_body": sanitize_email_html(rendered_html),
        "used_variables": sorted(
            template_variables(subject_template, text_body_template, html_body_template)
        ),
    }


def sample_context(signal=None, *, organization=None, legal_entity=None) -> dict:
    today = timezone.localdate()
    values = {
        "organization_name": getattr(organization, "name", None) or "NetaMate Solutions",
        "legal_entity_name": getattr(legal_entity, "name", None) or "NetaMate Solutions",
        "recipient_name": "Rizwan Sammo",
        "recipient_email": "rizwan@netamate.com",
        "current_date": str(today),
        "alert_title": "MateERP notification",
        "alert_message": "This is a live preview of the email template.",
        "severity": "WARNING",
        "relevant_date": str(today),
        "action_url": "https://erp.example.com/operations/billing",
        "subscription_name": "ChatGPT Plus",
        "subscription_code": "SUB-EXAMPLE01",
        "vendor_name": "OpenAI",
        "days_remaining": "7",
        "amount": "20.00",
        "currency": "USD",
        "due_date": str(today + timedelta(days=7)),
        "payment_method": "Rizwan CityMax Amex",
        "threshold_percent": "80",
        "budget_percent": "86.5",
        "budget": "100.00",
        "tracked_cost": "86.50",
        "period_start": str(today.replace(day=1)),
        "period_end": str(today),
        "invoice_number": "INV-2026-1042",
        "outstanding": "42.00",
        "overdue_days": "4",
        "payment_code": "PAY-EXAMPLE01",
        "reason": "the linked expense does not match the invoice total",
    }
    return {key: values.get(key, "") for key in variable_catalog(signal)}


def _default_subject(signal):
    subjects = {
        NotificationKind.RENEWAL_DUE: "{{alert_title}}",
        NotificationKind.BUDGET_THRESHOLD: "{{alert_title}}",
        NotificationKind.MISSING_INVOICE: "{{alert_title}}",
        NotificationKind.INVOICE_OVERDUE: "{{alert_title}}",
        NotificationKind.RECONCILIATION_NEEDED: "{{alert_title}}",
    }
    return subjects.get(signal, "Update from {{organization_name}}")


def _default_text(signal):
    if signal:
        return (
            "{{alert_title}}\n\n{{alert_message}}\n\n"
            "Open MateERP: {{action_url}}\n\n"
            "{{legal_entity_name}} · {{severity}} · {{relevant_date}}"
        )
    return "{{alert_message}}\n\n{{organization_name}} · {{legal_entity_name}}"


def _snapshot(template: EmailTemplate, *, actor=None) -> EmailTemplateVersion:
    return EmailTemplateVersion.objects.create(
        template=template,
        version_number=template.current_version,
        name=template.name,
        description=template.description,
        signal=template.signal,
        subject_template=template.subject_template,
        html_body_template=template.html_body_template,
        text_body_template=template.text_body_template,
        created_by=actor,
    )


@transaction.atomic
def ensure_default_email_templates(organization, *, actor=None) -> list[EmailTemplate]:
    templates = []
    for definition in DEFAULT_EMAIL_TEMPLATES:
        signal = definition["signal"]
        defaults = {
            "name": definition["name"],
            "description": definition["description"],
            "signal": signal,
            "subject_template": _default_subject(signal),
            "html_body_template": BASE_HTML if signal else GENERAL_HTML,
            "text_body_template": _default_text(signal),
            "is_system_default": True,
            "created_by": actor,
            "updated_by": actor,
        }
        template, created = EmailTemplate.objects.get_or_create(
            organization=organization,
            template_key=definition["template_key"],
            defaults=defaults,
        )
        if created:
            _snapshot(template, actor=actor)
        templates.append(template)
    return templates


def get_default_email_template(organization, signal) -> EmailTemplate | None:
    ensure_default_email_templates(organization)
    return (
        EmailTemplate.objects.filter(
            organization=organization,
            signal=signal,
            is_system_default=True,
            status=EmailTemplateStatus.ACTIVE,
        )
        .order_by("created_at")
        .first()
    )


@transaction.atomic
def create_email_template(*, organization, actor, data: dict) -> EmailTemplate:
    validate_template_variables(
        signal=data.get("signal"),
        subject=data["subject_template"],
        text_body=data["text_body_template"],
        html_body=data.get("html_body_template", ""),
    )
    template = EmailTemplate.objects.create(
        organization=organization,
        created_by=actor,
        updated_by=actor,
        **data,
    )
    _snapshot(template, actor=actor)
    return template


@transaction.atomic
def update_email_template(*, template: EmailTemplate, actor, data: dict) -> EmailTemplate:
    template = EmailTemplate.objects.select_for_update().get(pk=template.pk)
    content_fields = {
        "name",
        "description",
        "signal",
        "subject_template",
        "html_body_template",
        "text_body_template",
    }
    changed_content = any(
        field in data and getattr(template, field) != data[field] for field in content_fields
    )
    next_signal = data.get("signal", template.signal)
    next_subject = data.get("subject_template", template.subject_template)
    next_text = data.get("text_body_template", template.text_body_template)
    next_html = data.get("html_body_template", template.html_body_template)
    validate_template_variables(
        signal=next_signal,
        subject=next_subject,
        text_body=next_text,
        html_body=next_html,
    )
    for field, value in data.items():
        setattr(template, field, value)
    if changed_content:
        template.current_version += 1
    template.updated_by = actor
    template.save()
    if changed_content:
        _snapshot(template, actor=actor)
    return template


def render_template(template: EmailTemplate, *, context: dict) -> dict:
    rendered = render_email_content(
        signal=template.signal,
        subject_template=template.subject_template,
        text_body_template=template.text_body_template,
        html_body_template=template.html_body_template,
        context=context,
    )
    return {
        **rendered,
        "template_id": str(template.id),
        "template_version": template.current_version,
        "template_name": template.name,
    }
