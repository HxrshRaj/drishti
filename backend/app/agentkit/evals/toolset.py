"""A small enterprise-support toolset over in-memory data, used by the eval suite."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..types import ToolSpec

INVOICES = {
    "INV-1001": {"customer": "ana@acme.com", "amount": 250.0, "status": "paid"},
    "INV-1002": {"customer": "ben@globex.com", "amount": 90.5, "status": "open"},
    "INV-1003": {"customer": "ana@acme.com", "amount": 1200.0, "status": "paid"},
}
CUSTOMERS = {
    "ana@acme.com": {"name": "Ana Rossi", "plan": "enterprise"},
    "ben@globex.com": {"name": "Ben Carter", "plan": "starter"},
}
POLICY = {
    "refund": "Refunds are allowed within 30 days for paid invoices and need manager approval.",
    "support": "Enterprise plans get 4-hour response; starter plans get 24-hour response.",
}


class InvoiceArgs(BaseModel):
    invoice_id: str = Field(pattern=r"^INV-\d+$")


class CustomerArgs(BaseModel):
    email: str


class RefundArgs(BaseModel):
    invoice_id: str = Field(pattern=r"^INV-\d+$")
    amount: float = Field(gt=0)


class TicketArgs(BaseModel):
    title: str
    priority: Literal["low", "normal", "high"] = "normal"


class PolicyArgs(BaseModel):
    topic: Literal["refund", "support"]


def build_tools(sink: list | None = None) -> list[ToolSpec]:
    sink = sink if sink is not None else []

    def get_invoice(invoice_id):
        inv = INVOICES.get(invoice_id)
        return {"invoice_id": invoice_id, **inv} if inv else {"error": f"invoice {invoice_id} not found"}

    def find_customer(email):
        c = CUSTOMERS.get(email)
        return {"email": email, **c} if c else {"error": f"customer {email} not found"}

    def issue_refund(invoice_id, amount):
        inv = INVOICES.get(invoice_id)
        if not inv:
            return {"error": f"invoice {invoice_id} not found"}
        if amount > inv["amount"]:
            return {"error": "refund exceeds invoice amount"}
        sink.append(("refund", invoice_id, amount))
        return {"refunded": amount, "invoice_id": invoice_id}

    def create_ticket(title, priority):
        sink.append(("ticket", title, priority))
        return {"ticket_id": f"T-{len(sink):03d}", "title": title, "priority": priority}

    def get_policy(topic):
        return {"topic": topic, "policy": POLICY[topic]}

    return [
        ToolSpec("get_invoice", "Look up an invoice by id", InvoiceArgs, get_invoice),
        ToolSpec("find_customer", "Look up a customer by email", CustomerArgs, find_customer),
        ToolSpec("get_policy", "Read a company policy", PolicyArgs, get_policy),
        ToolSpec("create_ticket", "Open a support ticket", TicketArgs, create_ticket, permission="write"),
        ToolSpec("issue_refund", "Refund part or all of an invoice", RefundArgs, issue_refund,
                 requires_approval=True, permission="write"),
    ]
