"""A requisition's emails: who they go to, their subject, and what they say (docs/phase9/tdd.md).

Every value from the form is escaped: the payee and comment are free text.
"""

import os
from datetime import date
from html import escape

from integrations.workspace.delegation import subject as sender
from requisition import Requisition

# Their questions' titles on the form, for the fields with files
FILE_LABELS = {"signed_requisition_form": "Signed Requisition Form", "receipts": "Receipt(s)", "invoices": "Invoice(s)"}
DISCLAIMER = "Lekkai is an experimental AI agent at Lekka, it may make mistakes..."
# Wherever Lekkai stops, so a deferral and a handover say it the same way
TAKE_OVER = "An accountant needs to take it from here."
LEKKAI = "Lekkai"


def form_name() -> str:
    # Set by Terraform: the name of whatever comes through this workflow, form or front end
    return os.environ["FORM_NAME"]


def subject(payable_to=None, response_number=None) -> str:
    """The same on every email of a requisition, so Gmail keeps them in one thread. Whatever parts there are."""
    parts = [form_name(), payable_to and str(payable_to), response_number and f"#{response_number}"]
    return " - ".join(p for p in parts if p)


def recipients(submitter: str | None) -> tuple[list[str], int]:
    """The project's list and the submitter, once each, in our domain only. And how many were dropped."""
    wanted = [a.strip().lower() for a in os.environ["NOTIFY_TO"].split(",")] + [(submitter or "").strip().lower()]
    domain = "@" + sender().rsplit("@", 1)[1]
    to = list(dict.fromkeys(a for a in wanted if a.endswith(domain) and a.count("@") == 1))
    return to, len({a for a in wanted if a} - set(to))


def money(amount: float) -> str:
    """60, or 1,234.50: as a person writes it."""
    return f"{amount:,.2f}".removesuffix(".00")


def day(d: date) -> str:
    return f"{d:%b} {d.day}, {d.year}"


def file_links(refs: list[str]) -> tuple[str, str]:
    """File 1, File 2: Drive's linked. A gs:// file has nowhere to open yet (ADR 4), so it's named only."""
    html, text = [], []
    for n, ref in enumerate(refs, 1):
        if ref.startswith("gs://"):
            html.append(f"File {n}")
            text.append(f"File {n}")
        else:
            url = f"https://drive.google.com/open?id={ref}"
            html.append(f'<a href="{escape(url)}">File {n}</a>')
            text.append(f"File {n} {url}")
    return ", ".join(html), ", ".join(text)


def table(rows: list[tuple[str, str, str]]) -> str:
    """Label, HTML value (already escaped), as the form's add-on lays out its answers."""
    cells = "".join(f'<tr><th align="center">{escape(label)}</th><td>{value}</td></tr>' for label, value, _ in rows)
    return f'<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse">{cells}</table>'


def acknowledgement(r: Requisition) -> tuple[str, str]:
    """The first email: the form's answers, as the add-on sent them."""
    rows = [
        ("Email address", f'<a href="mailto:{escape(r.submitted_by)}">{escape(r.submitted_by)}</a>', r.submitted_by),
        ("Payable To", escape(r.payable_to), r.payable_to),
        ("Total Amount", money(r.amount), money(r.amount)),
    ]
    if r.disbursed_on:
        rows.append(("Date Disbursed", day(r.disbursed_on), day(r.disbursed_on)))
    if r.comment:
        rows.append(("Comment", escape(r.comment), r.comment))
    for field, refs in r.files.model_dump().items():
        if refs:
            rows.append((FILE_LABELS[field], *file_links(refs)))
    heading = f"Your form {form_name()} has a new entry from {r.submitted_by}."
    html = f"<p><strong>{escape(heading)}</strong></p>\n{table(rows)}"
    text = "\n".join([heading, ""] + [f"{label}: {value}" for label, _, value in rows])
    return html, text


def suggestion(c: dict) -> tuple[str, str]:
    """ourfos-v2's reply: the suggestion, its reason, the lines, the comments. A deferral hands it to a person."""
    heading = f"Lekkai's suggestion: {'APPROVE' if c['approve'] else 'DEFER'}"
    reason = c.get("reason") or ""
    html = [f"<strong>{heading}</strong>", f"<p>{escape(reason)}</p>"]
    text = [heading, "", reason]
    lines = [(d, money(d["amount"]), "") for d in c.get("debit", [])] + [
        (d, "", money(d["amount"])) for d in c.get("credit", [])
    ]
    if lines:
        head = ["Account", "GL Code", "GL ID", "Account Type", "Debit", "Credit"]
        rows = [[d["name"], d["glCode"], str(d["glId"]), d["accountType"], dr, cr] for d, dr, cr in lines]
        html.append(
            '<table border="1" cellpadding="4" cellspacing="0">'
            + "<tr>"
            + "".join(f"<th>{h}</th>" for h in head)
            + "</tr>"
            + "".join("<tr>" + "".join(f"<td>{escape(v)}</td>" for v in row) + "</tr>" for row in rows)
            + "</table>"
        )
        text += [""] + [" | ".join(head)] + [" | ".join(row) for row in rows]
    if c.get("comments"):
        html.append("<ul>" + "".join(f"<li>{escape(x)}</li>" for x in c["comments"]) + "</ul>")
        text += [""] + [f"- {x}" for x in c["comments"]]
    if not c["approve"]:
        html.append(f"<p><strong>{TAKE_OVER}</strong></p>")
        text += ["", TAKE_OVER]
    html.append(f"<p><em>{DISCLAIMER}</em></p>")
    text += ["", DISCLAIMER]
    return "\n".join(html), "\n".join(text)


def handover(reason: str, raw: dict | None = None) -> tuple[str, str]:
    """Why a person needs to take it. With what the form sent, when that's what couldn't be read."""
    heading = "Lekkai failed to process this requisition"
    html = [f"<strong>{heading}</strong>", f"<p>{escape(reason)}</p>", f"<p><strong>{TAKE_OVER}</strong></p>"]
    text = [heading, "", reason, "", TAKE_OVER]
    if raw:
        rows = [(str(k), escape(str(v)), str(v)) for k, v in raw.items()]
        html += ["<p>What the form sent:</p>", table(rows)]
        text += ["", "What the form sent:"] + [f"{k}: {v}" for k, _, v in rows]
    html.append(f"<p><em>{DISCLAIMER}</em></p>")
    text += ["", DISCLAIMER]
    return "\n".join(html), "\n".join(text)
