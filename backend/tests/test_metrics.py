"""Financial calculations are verified against hand-computed expected values."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models import CashAccount, Customer, Expense, Invoice, Payment, Subscription
from app.services.companies import create_company_with_owner
from app.services.metrics import Period, add_months, dashboard, pct_change
from tests.conftest import STRONG_PASSWORD

TODAY = date(2026, 6, 20)


def at(y, m, d, h=12) -> datetime:
    return datetime(y, m, d, h, tzinfo=UTC)


@pytest.fixture
def company(db):
    company, _ = create_company_with_owner(
        db, company_name="Calc Co", owner_full_name="Cal", owner_email="cal@example.com", owner_password=STRONG_PASSWORD
    )
    db.query(CashAccount).filter_by(company_id=company.id).one().opening_balance = Decimal("100000.00")
    db.query(CashAccount).filter_by(company_id=company.id).one().opening_date = date(2026, 1, 1)
    cid = company.id
    c1 = Customer(company_id=cid, name="A", acquired_on=date(2026, 5, 10))
    c2 = Customer(company_id=cid, name="B", acquired_on=date(2026, 6, 2))
    c3 = Customer(company_id=cid, name="C", acquired_on=date(2026, 6, 5), status="churned")
    db.add_all([c1, c2, c3])
    db.flush()

    def pay(amount, when, status="succeeded", fee="0", refunded="0"):
        db.add(
            Payment(
                company_id=cid,
                customer_id=c1.id,
                gateway="sandbox",
                amount=Decimal(amount),
                fee=Decimal(fee),
                refunded_amount=Decimal(refunded),
                status=status,
                occurred_at=when,
            )
        )

    # March, April, May: steady history for burn
    for m in (3, 4, 5):
        pay("20000.00", at(2026, m, 15), fee="400.00")
        db.add(Expense(company_id=cid, category="Payroll", amount=Decimal("50000.00"), expense_date=date(2026, m, 28)))
    # June (current period)
    pay("30000.00", at(2026, 6, 3), fee="600.00")
    pay("10000.00", at(2026, 6, 10), status="partially_refunded", fee="200.00", refunded="2500.00")
    pay("5000.00", at(2026, 6, 11), status="refunded", fee="100.00", refunded="5000.00")
    pay("8000.00", at(2026, 6, 12), status="failed")
    pay("7000.00", at(2026, 6, 13), status="pending")
    pay("4000.00", at(2026, 6, 14), status="disputed")
    db.add_all(
        [
            Expense(company_id=cid, category="Hosting", amount=Decimal("6000.00"), expense_date=date(2026, 6, 5), is_cogs=True),
            Expense(company_id=cid, category="Rent", amount=Decimal("15000.00"), expense_date=date(2026, 6, 1)),
            Expense(
                company_id=cid,
                category="Software",
                amount=Decimal("3000.00"),
                expense_date=date(2026, 6, 15),
                status="unpaid",
                due_date=date(2026, 7, 15),
            ),
        ]
    )
    db.add_all(
        [
            Invoice(
                company_id=cid,
                customer_id=c1.id,
                number="INV-1",
                issue_date=date(2026, 5, 1),
                due_date=date(2026, 5, 31),
                subtotal=Decimal("10000"),
                tax_total=Decimal("1800"),
                total=Decimal("11800"),
                amount_paid=Decimal("1800"),
                status="partially_paid",
            ),
            Invoice(
                company_id=cid,
                customer_id=c2.id,
                number="INV-2",
                issue_date=date(2026, 6, 15),
                due_date=date(2026, 7, 15),
                subtotal=Decimal("5000"),
                tax_total=Decimal("900"),
                total=Decimal("5900"),
                status="issued",
            ),
            Invoice(
                company_id=cid,
                customer_id=c2.id,
                number="INV-3",
                issue_date=date(2026, 6, 1),
                due_date=date(2026, 6, 10),
                subtotal=Decimal("100"),
                total=Decimal("100"),
                amount_paid=Decimal("100"),
                status="paid",
            ),
        ]
    )
    db.add_all(
        [
            Subscription(
                company_id=cid,
                customer_id=c1.id,
                plan_name="Pro",
                amount=Decimal("3000"),
                interval="month",
                started_on=date(2026, 1, 1),
            ),
            Subscription(
                company_id=cid,
                customer_id=c2.id,
                plan_name="Pro",
                amount=Decimal("9000"),
                interval="quarter",
                started_on=date(2026, 1, 1),
            ),
            Subscription(
                company_id=cid,
                customer_id=c2.id,
                plan_name="Ent",
                amount=Decimal("120000"),
                interval="year",
                started_on=date(2026, 1, 1),
            ),
            Subscription(
                company_id=cid,
                customer_id=c1.id,
                plan_name="Old",
                amount=Decimal("999"),
                interval="month",
                status="cancelled",
                started_on=date(2026, 1, 1),
            ),
        ]
    )
    db.commit()
    return company


def test_pct_change():
    assert pct_change(Decimal("120"), Decimal("100")) == Decimal("20.0")
    assert pct_change(Decimal("82"), Decimal("100")) == Decimal("-18.0")
    assert pct_change(Decimal("5"), Decimal("0")) is None


def test_add_months():
    assert add_months(date(2026, 11, 1), 3) == date(2027, 2, 1)
    assert add_months(date(2026, 1, 1), -1) == date(2025, 12, 1)


def test_period_previous():
    p = Period(date(2026, 6, 1), date(2026, 6, 20))
    assert p.previous() == Period(date(2026, 5, 12), date(2026, 5, 31))


def test_dashboard_figures(db, company):
    m = dashboard(db, company, today=TODAY)
    k = m["kpis"]
    # Revenue June 1-20: 30000 + (10000-2500) + (5000-5000) = 37500 ; failed/pending/disputed excluded
    assert k["revenue"]["value"] == "37500.00"
    # Fees: 600 + 200 + 100
    assert k["transaction_fees"]["value"] == "900.00"
    # Expenses dated in June: 6000 + 15000 + 3000 = 24000, plus fees 900
    assert k["expenses"]["value"] == "24900.00"
    assert k["net_profit"]["value"] == "12600.00"
    assert k["gross_profit"]["value"] == "31500.00"  # 37500 - 6000 COGS
    # Previous period May 12-31: May payment 20000 on 15th, fee 400; payroll 50000 on 28th
    assert k["revenue"]["previous"] == "20000.00"
    assert k["revenue"]["change_pct"] == "87.5"
    assert k["expenses"]["previous"] == "50400.00"

    # Cash: 100000 + net receipts since Jan 1 - paid expenses
    # receipts: 3*(20000-400) + (30000-600) + (10000-2500-200) + (5000-5000-100) = 58800 + 29400 + 7300 - 100 = 95400
    # paid expenses: 3*50000 + 6000 + 15000 = 171000
    assert k["cash_balance"]["value"] == "24400.00"

    # AR: INV-1 10000 (overdue), INV-2 5900; INV-3 paid excluded
    assert k["accounts_receivable"]["value"] == "15900.00"
    assert k["overdue_invoices"] == {"count": 1, "amount": "10000.00"}
    assert k["pending_invoices"] == {"count": 2, "amount": "15900.00"}
    assert k["accounts_payable"]["value"] == "3000.00"

    # MRR: 3000 + 9000/3 + 120000/12 = 16000 ; cancelled excluded
    assert k["mrr"]["value"] == "16000.00"
    assert k["arr"]["value"] == "192000.00"

    # Burn over Mar-May: each month out 50000, in 19600 -> net 30400
    assert k["net_burn"]["value"] == "30400.00"
    assert k["gross_burn"]["value"] == "50000.00"
    assert k["runway_months"]["value"] == "0.8"  # 24400 / 30400

    assert k["active_customers"]["value"] == 2
    assert k["new_customers"]["value"] == 2  # B and C acquired in June
    assert k["failed_payments"] == {"count": 1, "amount": "8000.00"}
    assert k["sales"]["count"] == 3

    june = next(x for x in m["charts"]["monthly"] if x["month"] == "2026-06")
    assert june["revenue"] == "37500.00"
    assert june["profit"] == "12600.00"
    assert sum(Decimal(d["revenue"]) for d in m["charts"]["daily_revenue"]) == Decimal("37500.00")
    cats = {c["category"]: c["amount"] for c in m["charts"]["expense_breakdown"]}
    assert cats == {"Rent": "15000.00", "Hosting": "6000.00", "Software": "3000.00", "Payment gateway fees": "900.00"}

    assert any("overdue" in s for s in m["summary"])
    assert any("below six months" in s for s in m["summary"])


def test_timezone_bucketing(db, company):
    # 20:00 UTC on 31 May is 01:30 on 1 June in Asia/Kolkata -> counts in June
    db.add(
        Payment(
            company_id=company.id, gateway="sandbox", amount=Decimal("1000"), status="succeeded", occurred_at=at(2026, 5, 31, 20)
        )
    )
    db.commit()
    m = dashboard(db, company, today=TODAY)
    assert m["kpis"]["revenue"]["value"] == "38500.00"


def test_empty_company_has_no_data(db):
    company, _ = create_company_with_owner(
        db, company_name="Empty", owner_full_name="E", owner_email="e@example.com", owner_password=STRONG_PASSWORD
    )
    db.commit()
    m = dashboard(db, company, today=TODAY)
    assert m["has_data"] is False
    assert m["summary"] == []
    assert m["kpis"]["runway_months"]["value"] is None
    assert m["kpis"]["revenue"]["change_pct"] is None


def test_summary_money_format():
    from app.services.metrics import _fmt

    assert _fmt(Decimal("624877.69"), "INR") == "₹6,24,877.69"
    assert _fmt(Decimal("12345678.5"), "INR") == "₹1,23,45,678.50"
    assert _fmt(Decimal("999"), "INR") == "₹999.00"
    assert _fmt(Decimal("-1234567.1"), "USD") == "-$1,234,567.10"
