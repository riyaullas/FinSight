"""Core financial entities used by the dashboard.

Phase 1 defines the records the executive dashboard is computed from. Phase 2 adds the
full payment ledger, accounting (chart of accounts, journal entries) and reconciliation.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import ZERO, Base, IdMixin, Money, TenantMixin, TimestampMixin, utcnow


class Customer(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))
    organisation: Mapped[str | None] = mapped_column(String(200))
    lead_source: Mapped[str | None] = mapped_column(String(100))
    # active | inactive | churned
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    acquired_on: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        CheckConstraint("status in ('active','inactive','churned')", name="status_valid"),
        Index("ix_customers_company_acquired", "company_id", "acquired_on"),
    )


class Invoice(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    number: Mapped[str] = mapped_column(String(50), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Money, default=ZERO, nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Money, default=ZERO, nullable=False)
    # draft | issued | partially_paid | paid | void
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)

    customer: Mapped[Customer] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("company_id", "number", name="uq_invoices_company_number"),
        CheckConstraint("status in ('draft','issued','partially_paid','paid','void')", name="status_valid"),
        CheckConstraint("total >= 0 and subtotal >= 0 and tax_total >= 0", name="amounts_non_negative"),
        CheckConstraint("amount_paid >= 0 and amount_paid <= total", name="paid_within_total"),
        CheckConstraint("due_date >= issue_date", name="due_after_issue"),
    )


class Payment(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    customer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="SET NULL"), index=True)
    # razorpay | stripe | cashfree | payu | bank | manual | sandbox
    gateway: Mapped[str] = mapped_column(String(20), nullable=False)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(100))
    reference: Mapped[str | None] = mapped_column(String(100))
    method: Mapped[str | None] = mapped_column(String(30))
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    fee: Mapped[Decimal] = mapped_column(Money, default=ZERO, nullable=False)
    refunded_amount: Mapped[Decimal] = mapped_column(Money, default=ZERO, nullable=False)
    # pending | succeeded | failed | refunded | partially_refunded | disputed
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # unreconciled | matched | mismatch
    reconciliation_status: Mapped[str] = mapped_column(String(20), default="unreconciled", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    customer: Mapped[Customer | None] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("company_id", "gateway", "gateway_payment_id", name="uq_payments_gateway_ref"),
        CheckConstraint(
            "status in ('pending','succeeded','failed','refunded','partially_refunded','disputed')",
            name="status_valid",
        ),
        CheckConstraint("amount > 0 and fee >= 0 and refunded_amount >= 0", name="amounts_valid"),
        CheckConstraint("refunded_amount <= amount", name="refund_within_amount"),
        Index("ix_payments_company_occurred", "company_id", "occurred_at"),
    )


class Expense(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "expenses"

    category: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str | None] = mapped_column(String(100))
    vendor_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    # paid | unpaid
    status: Mapped[str] = mapped_column(String(10), default="paid", nullable=False)
    # Cost of goods sold: counted against gross profit.
    is_cogs: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paid_on: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint("status in ('paid','unpaid')", name="status_valid"),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_expenses_company_date", "company_id", "expense_date"),
    )


class Subscription(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    # month | quarter | year
    interval: Mapped[str] = mapped_column(String(10), nullable=False)
    # active | past_due | cancelled
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    cancelled_on: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint("interval in ('month','quarter','year')", name="interval_valid"),
        CheckConstraint("status in ('active','past_due','cancelled')", name="status_valid"),
        CheckConstraint("amount > 0", name="amount_positive"),
    )


class CashAccount(IdMixin, TenantMixin, TimestampMixin, Base):
    """A bank or cash account with a known opening balance."""

    __tablename__ = "cash_accounts"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Money, default=ZERO, nullable=False)
    opening_date: Mapped[date] = mapped_column(Date, nullable=False)


class Alert(IdMixin, TenantMixin, Base):
    __tablename__ = "alerts"

    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # info | low | medium | high | critical
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detection_reason: Mapped[str | None] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    estimated_impact: Mapped[Decimal | None] = mapped_column(Money)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # open | acknowledged | resolved | dismissed
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("severity in ('info','low','medium','high','critical')", name="severity_valid"),
        CheckConstraint("status in ('open','acknowledged','resolved','dismissed')", name="status_valid"),
    )
