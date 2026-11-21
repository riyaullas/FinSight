"""Create a clearly-labelled demo company populated with synthetic data.

Usage:
    python -m app.scripts.seed_demo --email demo@example.com

The password is read interactively (or from DEMO_PASSWORD). All names, amounts and identifiers
are randomly generated; no real customer or financial information is used. The company is
flagged is_demo=True and the UI shows a "Demo data" banner for it.
"""

import argparse
import getpass
import os
import random
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.core.database import SessionLocal
from app.core.security import validate_password_strength
from app.models import CashAccount, Customer, Expense, Invoice, Payment, Subscription
from app.services.companies import CompanyError, create_company_with_owner

FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Isha", "Vikram", "Ananya", "Arjun", "Sara", "Neel", "Tara"]
ORG = ["Labs", "Retail", "Foods", "Logistics", "Studio", "Health", "Systems", "Traders", "Works", "Analytics"]
SOURCES = ["Website", "Referral", "Partner", "Outbound", "Event"]
CATEGORIES = [
    ("Payroll", False),
    ("Rent", False),
    ("Cloud hosting", True),
    ("Marketing", False),
    ("Software", False),
    ("Travel", False),
    ("Raw materials", True),
    ("Professional fees", False),
]
DEPARTMENTS = ["Engineering", "Sales", "Operations", "Marketing", "Finance"]


def _money(lo: int, hi: int, rng: random.Random) -> Decimal:
    return Decimal(rng.randrange(lo * 100, hi * 100)) / 100


def seed(email: str, password: str, months: int = 12, rng_seed: int = 7) -> None:
    rng = random.Random(rng_seed)  # noqa: S311 - synthetic data, not security sensitive
    db = SessionLocal()
    try:
        company, _ = create_company_with_owner(
            db,
            company_name="Demo Company (synthetic data)",
            owner_full_name="Demo Owner",
            owner_email=email,
            owner_password=password,
            is_demo=True,
        )
        company.onboarding_completed = True
        cid = company.id
        today = date.today()
        start = (today.replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)

        account = db.query(CashAccount).filter_by(company_id=cid).one()
        account.opening_balance = Decimal("2500000.00")
        account.opening_date = start

        customers: list[Customer] = []
        day = start
        while day <= today:
            for _ in range(rng.choice([1, 2, 2, 3, 4])):
                name = f"{rng.choice(FIRST)} {rng.choice(ORG)} (demo)"
                customers.append(
                    Customer(
                        company_id=cid,
                        name=name,
                        organisation=name,
                        lead_source=rng.choice(SOURCES),
                        email=f"contact{len(customers)}@demo.invalid",
                        acquired_on=min(day + timedelta(days=rng.randrange(0, 27)), today),
                        status=rng.choices(["active", "inactive", "churned"], [8, 1, 1])[0],
                    )
                )
            day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
        db.add_all(customers)
        db.flush()

        for c in customers:
            if rng.random() < 0.6:
                interval = rng.choices(["month", "quarter", "year"], [6, 2, 1])[0]
                base = {"month": 4999, "quarter": 13999, "year": 49999}[interval]
                db.add(
                    Subscription(
                        company_id=cid,
                        customer_id=c.id,
                        plan_name=rng.choice(["Starter", "Growth", "Scale"]),
                        amount=Decimal(base),
                        interval=interval,
                        started_on=c.acquired_on,
                        status="active" if c.status == "active" else "cancelled",
                    )
                )

        n = 0
        for offset in range((today - start).days + 1):
            d = start + timedelta(days=offset)
            eligible = [c for c in customers if c.acquired_on <= d]
            if not eligible:
                continue
            for _ in range(rng.randrange(0, 5)):
                n += 1
                amount = _money(800, 45000, rng)
                status = rng.choices(["succeeded", "failed", "pending", "partially_refunded", "refunded"], [86, 8, 2, 2, 2])[0]
                refunded = Decimal("0")
                if status == "refunded":
                    refunded = amount
                elif status == "partially_refunded":
                    refunded = (amount * Decimal("0.3")).quantize(Decimal("0.01"))
                gateway = rng.choice(["razorpay", "stripe", "cashfree", "payu"])
                db.add(
                    Payment(
                        company_id=cid,
                        customer_id=rng.choice(eligible).id,
                        gateway="sandbox",
                        method=rng.choice(["card", "upi", "netbanking"]),
                        gateway_payment_id=f"demo_{n:06d}",
                        reference=f"DEMO-{gateway[:3].upper()}-{n:06d}",
                        amount=amount,
                        fee=(amount * Decimal("0.02")).quantize(Decimal("0.01")) if status != "failed" else Decimal("0"),
                        refunded_amount=refunded,
                        status=status,
                        occurred_at=datetime(d.year, d.month, d.day, rng.randrange(3, 17), rng.randrange(60), tzinfo=UTC),
                    )
                )

        month = start
        while month <= today:
            for cat, cogs in CATEGORIES:
                base = {"Payroll": 420000, "Rent": 85000}.get(cat, 30000)
                exp_date = min(month + timedelta(days=rng.randrange(0, 27)), today)
                unpaid = (today - exp_date).days < 30 and rng.random() < 0.3
                db.add(
                    Expense(
                        company_id=cid,
                        category=cat,
                        is_cogs=cogs,
                        department=rng.choice(DEPARTMENTS),
                        vendor_name=f"{rng.choice(ORG)} Supplies (demo)",
                        amount=_money(int(base * 0.7), int(base * 1.3), rng),
                        expense_date=exp_date,
                        status="unpaid" if unpaid else "paid",
                        paid_on=None if unpaid else exp_date,
                        due_date=exp_date + timedelta(days=30),
                    )
                )
            month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)

        for i, c in enumerate(rng.sample(customers, min(40, len(customers)))):
            issue = max(c.acquired_on, today - timedelta(days=rng.randrange(5, 120)))
            subtotal = _money(5000, 90000, rng)
            tax = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
            total = subtotal + tax
            status = rng.choices(["issued", "partially_paid", "paid"], [4, 2, 4])[0]
            paid = (
                total
                if status == "paid"
                else ((total * Decimal("0.4")).quantize(Decimal("0.01")) if status == "partially_paid" else Decimal("0"))
            )
            db.add(
                Invoice(
                    company_id=cid,
                    customer_id=c.id,
                    number=f"DEMO-INV-{i + 1:04d}",
                    issue_date=issue,
                    due_date=issue + timedelta(days=30),
                    subtotal=subtotal,
                    tax_total=tax,
                    total=total,
                    amount_paid=paid,
                    status=status,
                )
            )
        db.commit()
        print(f"Demo company created for {email}: {len(customers)} customers, {n} payments.")
    except CompanyError as err:
        db.rollback()
        sys.exit(f"Error: {err}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--months", type=int, default=12)
    args = parser.parse_args()
    password = os.environ.get("DEMO_PASSWORD") or getpass.getpass("Password for the demo owner: ")
    try:
        validate_password_strength(password)
    except ValueError as err:
        sys.exit(f"Error: {err}")
    seed(args.email, password, args.months)


if __name__ == "__main__":
    main()
