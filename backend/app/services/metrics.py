"""Deterministic financial metrics for the executive dashboard.

Every figure here is computed from database records with Decimal arithmetic. The AI assistant
(Phase 5) reads these results; it never computes financial figures itself.

Definitions (see docs/METRICS.md for the full specification):
  * Revenue (cash basis)  = sum(amount - refunded_amount) of settled payments in the period.
                            Settled = succeeded, partially_refunded, refunded. Disputed and
                            failed/pending payments are excluded.
  * Transaction fees      = sum(fee) of settled payments in the period.
  * Expenses              = sum(amount) of expenses dated in the period, plus transaction fees.
  * Gross profit          = revenue - cost-of-goods-sold expenses.
  * Net profit            = revenue - expenses (including fees).
  * Cash balance          = opening balances + net receipts - paid expenses since the opening date.
  * Accounts receivable   = sum(total - amount_paid) of issued and partially-paid invoices.
  * Accounts payable      = sum(amount) of unpaid expenses.
  * MRR                   = active subscriptions normalised to a month (quarter/3, year/12).
  * Net burn              = mean over the last 3 complete months of (cash out - cash in), floored at 0.
  * Runway (months)       = cash balance / net burn; None when net burn is zero.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Alert, CashAccount, Company, Customer, Expense, Invoice, Payment, Subscription
from app.models.base import ZERO

SETTLED = ("succeeded", "partially_refunded", "refunded")
OPEN_INVOICE = ("issued", "partially_paid")
CENT = Decimal("0.01")


def q(v: Decimal | int | None) -> Decimal:
    return (Decimal(v) if v is not None else ZERO).quantize(CENT, rounding=ROUND_HALF_UP)


def pct_change(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return ((current - previous) / abs(previous) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def month_start(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


@dataclass(frozen=True)
class Period:
    start: date
    end: date  # inclusive

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def previous(self) -> Period:
        end = self.start - timedelta(days=1)
        return Period(end - timedelta(days=self.days - 1), end)


class Calculator:
    """Computes metrics for one company. All queries are filtered by company_id."""

    def __init__(self, db: Session, company: Company):
        self.db = db
        self.company = company
        self.cid: uuid.UUID = company.id
        try:
            self.tz = ZoneInfo(company.timezone)
        except Exception:  # noqa: BLE001 - unknown tz falls back to UTC
            self.tz = ZoneInfo("UTC")

    # ---- time helpers: local calendar dates -> UTC instants
    def _start_utc(self, d: date) -> datetime:
        return datetime.combine(d, time.min, self.tz).astimezone(UTC)

    def _end_utc(self, d: date) -> datetime:  # exclusive bound: start of the following day
        return self._start_utc(d + timedelta(days=1))

    def local_date(self, dt: datetime) -> date:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(self.tz).date()

    # ---- primitive aggregates
    def _settled_payments(self, start: date, end: date):
        return (
            Payment.company_id == self.cid,
            Payment.status.in_(SETTLED),
            Payment.occurred_at >= self._start_utc(start),
            Payment.occurred_at < self._end_utc(end),
        )

    def revenue(self, p: Period) -> Decimal:
        return q(
            self.db.scalar(
                select(func.sum(Payment.amount - Payment.refunded_amount)).where(*self._settled_payments(p.start, p.end))
            )
        )

    def fees(self, p: Period) -> Decimal:
        return q(self.db.scalar(select(func.sum(Payment.fee)).where(*self._settled_payments(p.start, p.end))))

    def expenses(self, p: Period, cogs_only: bool = False) -> Decimal:
        conds = [Expense.company_id == self.cid, Expense.expense_date >= p.start, Expense.expense_date <= p.end]
        if cogs_only:
            conds.append(Expense.is_cogs.is_(True))
        return q(self.db.scalar(select(func.sum(Expense.amount)).where(*conds)))

    def failed_payments(self, p: Period) -> tuple[int, Decimal]:
        row = self.db.execute(
            select(func.count(), func.sum(Payment.amount)).where(
                Payment.company_id == self.cid,
                Payment.status == "failed",
                Payment.occurred_at >= self._start_utc(p.start),
                Payment.occurred_at < self._end_utc(p.end),
            )
        ).one()
        return int(row[0] or 0), q(row[1])

    def cash_in(self, start: date, end: date) -> Decimal:
        return q(
            self.db.scalar(
                select(func.sum(Payment.amount - Payment.refunded_amount - Payment.fee)).where(
                    *self._settled_payments(start, end)
                )
            )
        )

    def cash_out(self, start: date, end: date) -> Decimal:
        paid_date = func.coalesce(Expense.paid_on, Expense.expense_date)
        return q(
            self.db.scalar(
                select(func.sum(Expense.amount)).where(
                    Expense.company_id == self.cid, Expense.status == "paid", paid_date >= start, paid_date <= end
                )
            )
        )

    def cash_balance(self, today: date) -> Decimal | None:
        accounts = self.db.scalars(select(CashAccount).where(CashAccount.company_id == self.cid)).all()
        if not accounts:
            return None
        opening = sum((a.opening_balance for a in accounts), ZERO)
        since = min(a.opening_date for a in accounts)
        return q(opening + self.cash_in(since, today) - self.cash_out(since, today))

    def receivables(self, today: date) -> dict:
        rows = self.db.execute(
            select(Invoice.total - Invoice.amount_paid, Invoice.due_date).where(
                Invoice.company_id == self.cid, Invoice.status.in_(OPEN_INVOICE)
            )
        ).all()
        total = sum((r[0] for r in rows), ZERO)
        overdue = [r for r in rows if r[1] < today]
        return {
            "total": q(total),
            "open_count": len(rows),
            "overdue_amount": q(sum((r[0] for r in overdue), ZERO)),
            "overdue_count": len(overdue),
        }

    def payables(self) -> Decimal:
        return q(
            self.db.scalar(select(func.sum(Expense.amount)).where(Expense.company_id == self.cid, Expense.status == "unpaid"))
        )

    def mrr(self) -> Decimal:
        rows = self.db.execute(
            select(Subscription.amount, Subscription.interval).where(
                Subscription.company_id == self.cid, Subscription.status == "active"
            )
        ).all()
        divisor = {"month": 1, "quarter": 3, "year": 12}
        return q(sum((amt / divisor[iv] for amt, iv in rows), ZERO))

    def burn(self, today: date) -> tuple[Decimal, Decimal]:
        """(net_burn, gross_burn) as monthly averages over the last 3 complete months."""
        first = add_months(month_start(today), -3)
        net_total = ZERO
        gross_total = ZERO
        for i in range(3):
            s = add_months(first, i)
            e = add_months(first, i + 1) - timedelta(days=1)
            out = self.cash_out(s, e)
            gross_total += out
            net_total += out - self.cash_in(s, e)
        return q(max(net_total / 3, ZERO)), q(gross_total / 3)

    def customer_counts(self, p: Period) -> dict:
        active = self.db.scalar(
            select(func.count()).select_from(Customer).where(Customer.company_id == self.cid, Customer.status == "active")
        )
        new = self.db.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.company_id == self.cid, Customer.acquired_on >= p.start, Customer.acquired_on <= p.end)
        )
        prev = p.previous()
        new_prev = self.db.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.company_id == self.cid, Customer.acquired_on >= prev.start, Customer.acquired_on <= prev.end)
        )
        return {"active": int(active or 0), "new": int(new or 0), "new_previous": int(new_prev or 0)}

    # ---- time series
    def daily_revenue(self, end: date, days: int = 30) -> list[dict]:
        start = end - timedelta(days=days - 1)
        rows = self.db.execute(
            select(Payment.occurred_at, Payment.amount - Payment.refunded_amount).where(*self._settled_payments(start, end))
        ).all()
        buckets = {start + timedelta(days=i): ZERO for i in range(days)}
        for occurred, amount in rows:
            d = self.local_date(occurred)
            if d in buckets:
                buckets[d] += amount
        return [{"date": d.isoformat(), "revenue": str(q(v))} for d, v in buckets.items()]

    def monthly(self, today: date, months: int = 12) -> list[dict]:
        first = add_months(month_start(today), -(months - 1))
        out = []
        for i in range(months):
            s = add_months(first, i)
            e = min(add_months(first, i + 1) - timedelta(days=1), today)
            p = Period(s, e)
            rev = self.revenue(p)
            exp = self.expenses(p) + self.fees(p)
            cin = self.cash_in(s, e)
            cout = self.cash_out(s, e)
            new_customers = self.db.scalar(
                select(func.count())
                .select_from(Customer)
                .where(Customer.company_id == self.cid, Customer.acquired_on >= s, Customer.acquired_on <= e)
            )
            out.append(
                {
                    "month": s.strftime("%Y-%m"),
                    "revenue": str(rev),
                    "expenses": str(q(exp)),
                    "profit": str(q(rev - exp)),
                    "cash_in": str(cin),
                    "cash_out": str(cout),
                    "net_cash": str(q(cin - cout)),
                    "new_customers": int(new_customers or 0),
                }
            )
        return out

    def expense_breakdown(self, p: Period) -> list[dict]:
        rows = self.db.execute(
            select(Expense.category, func.sum(Expense.amount))
            .where(Expense.company_id == self.cid, Expense.expense_date >= p.start, Expense.expense_date <= p.end)
            .group_by(Expense.category)
        ).all()
        fees = self.fees(p)
        items = [(c, q(a)) for c, a in rows]
        if fees > 0:
            items.append(("Payment gateway fees", fees))
        items.sort(key=lambda x: x[1], reverse=True)
        return [{"category": c, "amount": str(a)} for c, a in items]

    def recent_transactions(self, limit: int = 8) -> list[dict]:
        rows = self.db.scalars(
            select(Payment).where(Payment.company_id == self.cid).order_by(Payment.occurred_at.desc()).limit(limit)
        ).all()
        return [
            {
                "id": str(p.id),
                "occurred_at": (p.occurred_at if p.occurred_at.tzinfo else p.occurred_at.replace(tzinfo=UTC)).isoformat(),
                "customer": p.customer.name if p.customer else None,
                "gateway": p.gateway,
                "method": p.method,
                "amount": str(q(p.amount)),
                "status": p.status,
                "reference": p.reference,
            }
            for p in rows
        ]

    def recent_alerts(self, limit: int = 5) -> list[dict]:
        rows = self.db.scalars(
            select(Alert)
            .where(Alert.company_id == self.cid, Alert.status.in_(("open", "acknowledged")))
            .order_by(Alert.detected_at.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": str(a.id),
                "severity": a.severity,
                "title": a.title,
                "description": a.description,
                "estimated_impact": str(q(a.estimated_impact)) if a.estimated_impact is not None else None,
                "detected_at": (a.detected_at if a.detected_at.tzinfo else a.detected_at.replace(tzinfo=UTC)).isoformat(),
            }
            for a in rows
        ]

    def has_data(self) -> bool:
        for model in (Payment, Expense, Invoice, Customer):
            if self.db.scalar(select(model.id).where(model.company_id == self.cid).limit(1)) is not None:
                return True
        return False


def _money(v: Decimal | None) -> str | None:
    return None if v is None else str(q(v))


def _indian_grouping(whole: str) -> str:
    """1234567 -> 12,34,567 (lakh/crore grouping)."""
    if len(whole) <= 3:
        return whole
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def _fmt(v: Decimal, currency: str) -> str:
    symbol = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get(currency, currency + " ")
    sign = "-" if v < 0 else ""
    whole, frac = f"{abs(q(v)):.2f}".split(".")
    grouped = _indian_grouping(whole) if currency == "INR" else f"{int(whole):,}"
    return f"{sign}{symbol}{grouped}.{frac}"


def build_summary(m: dict, currency: str) -> list[str]:
    """Deterministic, rule-based statements derived from computed metrics only."""
    lines: list[str] = []
    k = m["kpis"]
    rev, prev = Decimal(k["revenue"]["value"]), Decimal(k["revenue"]["previous"])
    change = k["revenue"]["change_pct"]
    if change is not None:
        direction = "up" if Decimal(change) >= 0 else "down"
        lines.append(
            f"Revenue is {direction} {abs(Decimal(change))}% versus the previous period ({_fmt(rev, currency)} vs {_fmt(prev, currency)})."
        )
    elif rev > 0:
        lines.append(f"Revenue for the period is {_fmt(rev, currency)}; there is no prior-period revenue to compare against.")
    net = Decimal(k["net_profit"]["value"])
    lines.append(f"Net {'profit' if net >= 0 else 'loss'} for the period is {_fmt(abs(net), currency)}.")
    ar = m["receivables"]
    if ar["overdue_count"]:
        lines.append(
            f"{ar['overdue_count']} invoice(s) are overdue, totalling {_fmt(Decimal(ar['overdue_amount']), currency)}. Consider following up with these customers."
        )
    runway = k["runway_months"]["value"]
    if runway is not None:
        rm = Decimal(runway)
        lines.append(
            f"At the current net burn, cash runway is {rm} months."
            + (" This is below six months; review spending and collections." if rm < 6 else "")
        )
    elif Decimal(k["net_burn"]["value"]) == 0 and k["cash_balance"]["value"] is not None:
        lines.append("Cash inflows covered outflows over the last three months, so there is no net burn.")
    failed = k["failed_payments"]
    if failed["count"]:
        lines.append(f"{failed['count']} payment(s) failed in the period, worth {_fmt(Decimal(failed['amount']), currency)}.")
    return lines


def dashboard(db: Session, company: Company, period: Period | None = None, today: date | None = None) -> dict:
    c = Calculator(db, company)
    today = today or datetime.now(c.tz).date()
    period = period or Period(month_start(today), today)
    prev = period.previous()

    rev, rev_prev = c.revenue(period), c.revenue(prev)
    fees, fees_prev = c.fees(period), c.fees(prev)
    exp, exp_prev = c.expenses(period) + fees, c.expenses(prev) + fees_prev
    cogs, cogs_prev = c.expenses(period, cogs_only=True), c.expenses(prev, cogs_only=True)
    net, net_prev = rev - exp, rev_prev - exp_prev
    gross, gross_prev = rev - cogs, rev_prev - cogs_prev
    cash = c.cash_balance(today)
    net_burn, gross_burn = c.burn(today)
    runway = (cash / net_burn).quantize(Decimal("0.1")) if (cash is not None and net_burn > 0) else None
    mrr = c.mrr()
    ar = c.receivables(today)
    customers = c.customer_counts(period)
    failed_count, failed_amount = c.failed_payments(period)
    sales_count = db.scalar(select(func.count()).select_from(Payment).where(*c._settled_payments(period.start, period.end))) or 0

    def kpi(value: Decimal, previous: Decimal) -> dict:
        return {"value": str(q(value)), "previous": str(q(previous)), "change_pct": _str(pct_change(value, previous))}

    result = {
        "currency": company.currency,
        "is_demo": company.is_demo,
        "has_data": c.has_data(),
        "period": {"start": period.start.isoformat(), "end": period.end.isoformat()},
        "previous_period": {"start": prev.start.isoformat(), "end": prev.end.isoformat()},
        "as_of": today.isoformat(),
        "kpis": {
            "revenue": kpi(rev, rev_prev),
            "expenses": kpi(exp, exp_prev),
            "net_profit": kpi(net, net_prev),
            "gross_profit": kpi(gross, gross_prev),
            "transaction_fees": kpi(fees, fees_prev),
            "cash_balance": {"value": _money(cash)},
            "accounts_receivable": {"value": str(ar["total"])},
            "accounts_payable": {"value": str(c.payables())},
            "mrr": {"value": str(mrr)},
            "arr": {"value": str(q(mrr * 12))},
            "net_burn": {"value": str(net_burn)},
            "gross_burn": {"value": str(gross_burn)},
            "runway_months": {"value": _str(runway)},
            "active_customers": {"value": customers["active"]},
            "new_customers": {
                "value": customers["new"],
                "previous": customers["new_previous"],
                "change_pct": _str(pct_change(Decimal(customers["new"]), Decimal(customers["new_previous"]))),
            },
            "pending_invoices": {"count": ar["open_count"], "amount": str(ar["total"])},
            "overdue_invoices": {"count": ar["overdue_count"], "amount": str(ar["overdue_amount"])},
            "failed_payments": {"count": failed_count, "amount": str(failed_amount)},
            "sales": {
                "count": int(sales_count),
                "average_value": str(q(rev / sales_count)) if sales_count else "0.00",
            },
        },
        "receivables": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in ar.items()},
        "charts": {
            "daily_revenue": c.daily_revenue(today),
            "monthly": c.monthly(today),
            "expense_breakdown": c.expense_breakdown(period),
        },
        "recent_transactions": c.recent_transactions(),
        "recent_alerts": c.recent_alerts(),
    }
    result["summary"] = build_summary(result, company.currency) if result["has_data"] else []
    return result


def _str(v: Decimal | None) -> str | None:
    return None if v is None else str(v)
