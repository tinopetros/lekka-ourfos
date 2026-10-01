"""Every form's emails: who they go to, their subject, and what they say (docs/phase9/tdd.md, docs/phase10/tdd.md).

Every value from a form is escaped: most of them are free text.
"""

import json
import os
import re
from datetime import date
from functools import cache
from html import escape

from forms import FORMS
from integrations.workspace.delegation import subject as sender
from requisition import Requisition
from submission import Submission

# Their questions' titles on the form, for the fields with files
FILE_LABELS = {"signed_requisition_form": "Signed Requisition Form", "receipts": "Receipt(s)", "invoices": "Invoice(s)"}
DISCLAIMER = "Lekkai is an experimental AI agent at Lekka, it may make mistakes..."
# Where Lekkai stops on a requisition, so a deferral says it as the handover does
TAKE_OVER = f"{FORMS['requisition'].taker.capitalize()} needs to take it from here."
LEKKAI = "Lekkai"
# An answer that's only a link, like a loan's client folder, is linked
URL = re.compile(r"^https?://\S+$")


@cache
def config() -> dict:
    """Set by Terraform, per form: its name, who hears, and where replies go."""
    return json.loads(os.environ["FORMS"])


def form_name(form: str) -> str:
    # The name of whatever comes through, form or front end
    return config()[form]["name"]


def names(form: str, answers: dict) -> str | None:
    """What the subject names, after the form: a payee, a trip, an applicant."""
    return " ".join(str(answers[k]).strip() for k in FORMS[form].subject if answers.get(k)) or None


def subject(form: str, name=None, response_number=None, test=False) -> str:
    """The same on every email of a submission, so Gmail keeps them in one thread. Whatever parts there are."""
    parts = [form_name(form), name and str(name), response_number and f"#{response_number}"]
    return ("[TEST] " if test else "") + " - ".join(p for p in parts if p)


def reply_to(form: str, test=False) -> list[str]:
    """Only where a form's replies go elsewhere, the loan's to its directors. A test's go to lekkai@ alone."""
    listed = config()[form].get("reply_to") or []
    return [sender()] if listed and test else listed


def recipients(form: str, submitter: str | None, test=False) -> tuple[list[str], int]:
    """The form's list, or lekkai@ alone for a test, and the submitter, once each, in our domain only. And how
    many were dropped (docs/release1/adr.md 3)."""
    listed = [sender()] if test else config()[form]["notify_to"]
    wanted = [a.strip().lower() for a in listed] + [(submitter or "").strip().lower()]
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


# One look for every table, whichever email it's in: the form add-on's, light and roomy. Styles inline, since
# Gmail drops <style>. The email's own font, inherited: a table doesn't always inherit it unasked. A value wraps
# rather than stretch the table, so a long comment stays readable
TABLE = '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-family:inherit;font-size:inherit">'
CELL = "border:1px solid #e3e3e3;background:#f9f9f9;padding:10px 20px"
TH = f'<th style="{CELL};text-align:center">'
TD = f'<td style="{CELL};max-width:400px;word-wrap:break-word">'


def table(rows: list[tuple[str, str, str]]) -> str:
    """Label, HTML value (already escaped), as the form's add-on lays out its answers."""
    cells = "".join(f"<tr>{TH}{escape(label)}</th>{TD}{value}</td></tr>" for label, value, _ in rows)
    return f"{TABLE}{cells}</table>"


def acknowledgement(form: str, s: Submission) -> tuple[str, str]:
    """The first email: the form's answers, as its add-on sent them."""
    rows = requisition_rows(s) if isinstance(s, Requisition) else text_rows(form, s)
    heading = f"{form_name(form)} has a new entry from {s.submitted_by}:"
    html = f"<p><strong>{escape(heading)}</strong></p>\n{table(rows)}"
    text = "\n".join([heading, ""] + [f"{label}: {value}" for label, _, value in rows])
    return html, text


def submitter_row(s: Submission) -> tuple[str, str, str]:
    return ("Email address", f'<a href="mailto:{escape(s.submitted_by)}">{escape(s.submitted_by)}</a>', s.submitted_by)


def text_rows(form: str, s: Submission) -> list[tuple[str, str, str]]:
    """The form's questions in its order, empty ones left out. A line break stays one, and a lone link is linked."""
    spec, rows = FORMS[form], [submitter_row(s)]
    for key, label in spec.labels.items():
        value = getattr(s, key)
        if not value:
            continue
        if key in spec.files:
            rows.append((label, *file_links(value)))
        elif URL.match(value):
            rows.append((label, f'<a href="{escape(value)}">{escape(value)}</a>', value))
        else:
            rows.append((label, escape(value).replace("\n", "<br>"), value))
    return rows


def requisition_rows(r: Requisition) -> list[tuple[str, str, str]]:
    rows = [
        submitter_row(r),
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
    return rows


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
            TABLE
            + "<tr>"
            + "".join(f"{TH}{h}</th>" for h in head)
            + "</tr>"
            + "".join("<tr>" + "".join(f"{TD}{escape(v)}</td>" for v in row) + "</tr>" for row in rows)
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


def handover(form: str, reason: str, raw: dict | None = None) -> tuple[str, str]:
    """Why a person needs to take it. With what the form sent, when that's what couldn't be read."""
    spec = FORMS[form]
    heading = f"Lekkai failed to process this {spec.noun}: {spec.taker} needs to take it from here."
    html = [f"<strong>{heading}</strong>", f"<p>{escape(reason)}</p>"]
    text = [heading, "", reason]
    if raw:
        rows = [(str(k), escape(str(v)), str(v)) for k, v in raw.items()]
        html += ["<p>What the form sent:</p>", table(rows)]
        text += ["", "What the form sent:"] + [f"{k}: {v}" for k, _, v in rows]
    html.append(f"<p><em>{DISCLAIMER}</em></p>")
    text += ["", DISCLAIMER]
    return "\n".join(html), "\n".join(text)
