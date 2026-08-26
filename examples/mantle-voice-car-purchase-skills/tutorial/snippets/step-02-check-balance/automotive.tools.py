"""Shared Rasa Motors tools available via import_tools."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import cars as inventory
from lib.database import Database, get_user_id, resolve_username
from lib.financing import DEFAULT_TERM_MONTHS, MockFinancingAPI

APPOINTMENT_TIMES = ("09:00", "11:00", "14:00", "16:00")
APPOINTMENT_DURATION_MINUTES = 45
SEEDED_CREDIT_SCORES = {"alex rivera": 720}


def _username(context: Optional[ToolContext]) -> str:
    if context is None:
        return resolve_username()
    return resolve_username(context.memory.get("username"))


def _memory_value(context: Optional[ToolContext], key: str) -> Any:
    if context is None:
        return None
    return context.memory.get(key)


def _set(context: Optional[ToolContext], key: str, value: Any) -> None:
    if context is not None:
        context.memory.set(key, value)


def _end_time(start_time: str) -> str:
    start = datetime.strptime(start_time, "%H:%M")
    return (start + timedelta(minutes=APPOINTMENT_DURATION_MINUTES)).strftime("%H:%M")


def _as_car(car: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "model": car["model"],
        "type": car["type"],
        "price": float(car["price"]),
        "new_or_used": car["new_or_used"],
        "dealer_name": car["dealer_location"],
        "features": car.get("features", []),
    }


# ---------------------------------------------------------------------------
# Customer profile and accounts
# ---------------------------------------------------------------------------


@tool(description="Load the demo customer profile into project memory.")
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    """Ensure username / segment / contact details are available."""
    username = _username(context)
    db = Database()
    row = db.run_query(
        "SELECT name, segment, email, address FROM users WHERE name = ?",
        (username,),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={"ok": False, "error": "customer_not_found", "username": username}
        )

    name, segment, email, address = row
    _set(context, "username", name)
    _set(context, "segment", segment)
    _set(context, "email_address", email)
    _set(context, "physical_address", address)

    return ToolResult(
        llm_response={
            "ok": True,
            "username": name,
            "segment": segment,
            "email_address": email,
            "physical_address": address,
        }
    )


@tool(description="List the customer's bank accounts with balances.")
async def list_accounts(context: ToolContext = None) -> ToolResult:
    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    rows = db.run_query(
        "SELECT number, type, balance FROM accounts WHERE user_id = ?",
        (user_id,),
        one_record=False,
    )
    accounts = [
        {"account_number": number, "type": acc_type, "balance": float(balance)}
        for number, acc_type, balance in rows or []
    ]
    return ToolResult(
        llm_response={"ok": True, "accounts": accounts, "account_count": len(accounts)}
    )


@tool(description="Look up account balance by account number for the current customer.")
async def check_balance(account_number: str, context: ToolContext = None) -> ToolResult:
    """Look up account balance by account number.

    Args:
        account_number: The customer's account number (digits).
    """
    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    row = db.run_query(
        "SELECT balance, type FROM accounts WHERE user_id = ? AND number = ?",
        (user_id, account_number),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "account_not_found",
                "account_number": account_number,
                "hint": "Ask the customer for a valid account number from their accounts.",
            }
        )

    balance, acc_type = row
    _set(context, "account_number", account_number)
    _set(context, "account_balance", float(balance))

    return ToolResult(
        llm_response={
            "ok": True,
            "account_number": account_number,
            "account_type": acc_type,
            "balance": float(balance),
            "currency": "USD",
        }
    )


# ---------------------------------------------------------------------------
# Inventory research
# ---------------------------------------------------------------------------


@tool(description="Search the Rasa Motors inventory by model, body type, dealer, condition, or budget.")
async def search_cars(
    model: str = "",
    car_type: str = "",
    dealer_name: str = "",
    new_or_used: str = "",
    max_price: float = 0.0,
    context: ToolContext = None,
) -> ToolResult:
    """Search the dealership inventory.

    Args:
        model: Full or partial model name, for example "RAV4".
        car_type: Body type such as sedan, compact SUV, truck, EV, minivan.
        dealer_name: Restrict results to one dealer.
        new_or_used: Either "new" or "used".
        max_price: Highest price the customer will consider, 0 for no limit.
    """
    results = inventory.search_inventory(
        model=model or None,
        dealer=dealer_name or None,
        car_type=car_type or None,
        new_or_used=new_or_used or None,
        max_price=max_price or None,
        limit=8,
    )
    _set(context, "cars_searched", True)

    return ToolResult(
        llm_response={
            "ok": True,
            "cars": [_as_car(car) for car in results],
            "result_count": len(results),
            "available_types": inventory.list_types(),
            "hint": (
                "No inventory matched those filters. Offer to widen the budget or body type."
                if not results
                else "Read out at most three cars at a time for voice."
            ),
        }
    )


@tool(description="Recommend cars that fit a budget and body type, with supporting review snippets.")
async def recommend_cars(
    budget: float = 0.0,
    car_type: str = "",
    preference: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Recommend the best inventory matches for a customer's requirements.

    Args:
        budget: Maximum amount the customer wants to spend, 0 for no limit.
        car_type: Preferred body type such as sedan, compact SUV, truck, EV.
        preference: Free text such as "good for family" or "long range electric".
    """
    matches = inventory.search_inventory(
        car_type=car_type or None,
        max_price=budget or None,
        limit=50,
    )

    # Within budget, closest to the top of it usually means best equipped.
    if budget:
        matches.sort(key=lambda car: abs(float(car["price"]) - float(budget)))
    top = matches[:3]

    query_parts = [part for part in (preference, car_type, "car buying advice") if part]
    snippets = inventory.get_search_snippets(" ".join(query_parts), limit=2)

    _set(context, "cars_recommended", bool(top))
    if car_type:
        _set(context, "preferred_type", car_type)
    if budget:
        _set(context, "budget", float(budget))

    return ToolResult(
        llm_response={
            "ok": True,
            "recommendations": [_as_car(car) for car in top],
            "recommendation_count": len(top),
            "research_snippets": snippets,
            "hint": (
                "Nothing in stock fits those requirements. Suggest raising the budget "
                "or a different body type."
                if not top
                else "Give one sentence per recommendation and say why it fits."
            ),
        }
    )


@tool(description="Check whether a specific car model is currently in stock, optionally at one dealer.")
async def check_availability(
    model: str, dealer_name: str = "", context: ToolContext = None
) -> ToolResult:
    """Check stock for a model.

    Args:
        model: Model the customer asked about.
        dealer_name: Optional dealer to narrow the check to.
    """
    listings = inventory.search_inventory(
        model=model, dealer=dealer_name or None, limit=10
    )
    available = bool(listings)
    _set(context, "car_available", available)

    return ToolResult(
        llm_response={
            "ok": True,
            "model": model,
            "available": available,
            "listings": [_as_car(car) for car in listings],
            "listing_count": len(listings),
            "hint": (
                "Not in stock. Offer similar cars with find_similar_cars."
                if not available
                else "Confirm the dealer and price before reserving."
            ),
        }
    )


@tool(description="Find comparable cars to a model, in the same class and price band.")
async def find_similar_cars(model: str, context: ToolContext = None) -> ToolResult:
    """Suggest alternatives to a model.

    Args:
        model: Model the customer was originally interested in.
    """
    similar = inventory.find_similar(model, limit=4)
    _set(context, "alternatives_offered", bool(similar))

    return ToolResult(
        llm_response={
            "ok": True,
            "model": model,
            "similar_cars": [_as_car(car) for car in similar],
            "similar_count": len(similar),
            "hint": (
                "That model is not in the inventory at all — ask the customer what "
                "body type and budget they have in mind."
                if not similar
                else "Offer two alternatives at a time for voice."
            ),
        }
    )


@tool(description="List Rasa Motors dealers, or the dealers holding a specific model.")
async def list_dealers(model: str = "", context: ToolContext = None) -> ToolResult:
    """List dealers.

    Args:
        model: Optional model — when given, only dealers holding it are returned.
    """
    if model:
        holdings = inventory.list_dealers_for_model(model)
        return ToolResult(
            llm_response={
                "ok": True,
                "model": model,
                "dealers": holdings,
                "dealer_count": len({item["dealer_name"] for item in holdings}),
            }
        )

    dealers = inventory.list_dealers()
    return ToolResult(
        llm_response={"ok": True, "dealers": dealers, "dealer_count": len(dealers)}
    )


# ---------------------------------------------------------------------------
# Reservations
# ---------------------------------------------------------------------------


@tool(description="Reserve a car for the customer at a dealer. This holds the vehicle.")
async def finalize_reservation(
    car_model: str,
    dealer_name: str,
    car_price: float = 0.0,
    reason: str = "purchase_intent",
    context: ToolContext = None,
) -> ToolResult:
    """Record a reservation against the customer's account.

    Args:
        car_model: Exact model being reserved.
        dealer_name: Dealer holding the car.
        car_price: Advertised price, 0 to take it from the inventory.
        reason: One of test_drive, purchase_intent, hold.
    """
    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    listings = inventory.search_inventory(model=car_model, dealer=dealer_name or None, limit=1)
    if not listings:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "car_not_available",
                "car_model": car_model,
                "dealer_name": dealer_name,
                "hint": "Check availability again or offer a similar car.",
            }
        )

    listing = listings[0]
    price = float(car_price) if car_price else float(listing["price"])
    resolved_dealer = dealer_name or listing["dealer_location"]
    reference = f"RES-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    db.cursor.execute(
        """
        INSERT INTO reservations
            (user_id, reference, car_model, dealer_name, car_price, reason, status)
        VALUES (?, ?, ?, ?, ?, ?, 'confirmed')
        """,
        (user_id, reference, listing["model"], resolved_dealer, price, reason),
    )
    db.commit()

    _set(context, "car_model", listing["model"])
    _set(context, "car_price", price)
    _set(context, "dealer_name", resolved_dealer)
    _set(context, "reserved", True)
    _set(context, "reservation_reference", reference)

    return ToolResult(
        llm_response={
            "ok": True,
            "reference": reference,
            "car_model": listing["model"],
            "dealer_name": resolved_dealer,
            "car_price": price,
            "reason": reason,
            "hold_days": 3,
        }
    )


# ---------------------------------------------------------------------------
# Dealer appointments
# ---------------------------------------------------------------------------


@tool(description="List available dealer appointment slots over the coming weekdays.")
async def query_available_slots(
    dealer_name: str = "", days_ahead: int = 7, context: ToolContext = None
) -> ToolResult:
    """Generate open appointment slots.

    Args:
        dealer_name: Dealer to check, defaults to the dealer already in memory.
        days_ahead: How many calendar days forward to look.
    """
    dealer = dealer_name or _memory_value(context, "dealer_name") or ""
    if not dealer:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "dealer_required",
                "dealers": inventory.list_dealers(),
                "hint": "Ask the customer which dealer they want to visit.",
            }
        )

    db = Database()
    booked_rows = db.run_query(
        "SELECT date, start_time FROM appointments WHERE dealer_name = ? AND status = 'booked'",
        (dealer,),
        one_record=False,
    )
    booked = {(row[0], row[1]) for row in booked_rows or []}

    slots: List[Dict[str, str]] = []
    day = date.today()
    for offset in range(1, max(int(days_ahead), 1) + 1):
        candidate = day + timedelta(days=offset)
        if candidate.weekday() >= 5:  # dealers are closed at weekends
            continue
        for start_time in APPOINTMENT_TIMES:
            iso_day = candidate.isoformat()
            if (iso_day, start_time) in booked:
                continue
            slots.append(
                {
                    "date": iso_day,
                    "weekday": candidate.strftime("%A"),
                    "start_time": start_time,
                    "end_time": _end_time(start_time),
                }
            )

    _set(context, "slots_loaded", True)
    return ToolResult(
        llm_response={
            "ok": True,
            "dealer_name": dealer,
            "slots": slots[:8],
            "slot_count": len(slots[:8]),
            "hint": "Offer two or three slots at a time for voice.",
        }
    )


@tool(description="Book a dealer appointment for the customer at a date and time.")
async def book_appointment(
    dealer_name: str,
    appointment_date: str,
    start_time: str,
    purpose: str = "test_drive",
    car_model: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Book a dealer visit.

    Args:
        dealer_name: Dealer the customer will visit.
        appointment_date: Date in YYYY-MM-DD format.
        start_time: Slot start time in HH:MM (24 hour) format.
        purpose: One of test_drive, paperwork, collection, valuation.
        car_model: Car the visit is about, defaults to the reserved car.
    """
    try:
        parsed_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
    except ValueError:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "invalid_date",
                "hint": "Use YYYY-MM-DD for the appointment date.",
            }
        )

    if not re.fullmatch(r"\d{2}:\d{2}", start_time or ""):
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "invalid_time",
                "hint": "Use HH:MM in 24 hour format, for example 14:00.",
            }
        )

    if parsed_date <= date.today():
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "date_not_in_future",
                "hint": "Pick a date from tomorrow onwards.",
            }
        )

    if parsed_date.weekday() >= 5:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "dealer_closed",
                "hint": "Dealers open Monday to Friday. Offer a weekday slot.",
            }
        )

    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    clash = db.run_query(
        """
        SELECT id FROM appointments
        WHERE dealer_name = ? AND date = ? AND start_time = ? AND status = 'booked'
        """,
        (dealer_name, appointment_date, start_time),
        one_record=True,
    )
    if clash:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "slot_taken",
                "hint": "Call query_available_slots again and offer a different time.",
            }
        )

    model = car_model or _memory_value(context, "car_model") or ""
    reference = f"APT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    end_time = _end_time(start_time)

    db.cursor.execute(
        """
        INSERT INTO appointments
            (user_id, reference, dealer_name, car_model, date, start_time, end_time, purpose, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'booked')
        """,
        (user_id, reference, dealer_name, model, appointment_date, start_time, end_time, purpose),
    )
    db.commit()

    _set(context, "appointment_booked", True)
    _set(context, "appointment_reference", reference)

    return ToolResult(
        llm_response={
            "ok": True,
            "reference": reference,
            "dealer_name": dealer_name,
            "car_model": model,
            "date": appointment_date,
            "weekday": parsed_date.strftime("%A"),
            "start_time": start_time,
            "end_time": end_time,
            "purpose": purpose,
        }
    )


# ---------------------------------------------------------------------------
# Credit and affordability
# ---------------------------------------------------------------------------


@tool(description="Validate the customer's identity before any credit check.")
async def validate_identity(
    full_name: str,
    ssn_last_four: str,
    date_of_birth: str,
    context: ToolContext = None,
) -> ToolResult:
    """Check identity details are well formed.

    Args:
        full_name: Customer's full legal name.
        ssn_last_four: Last four digits of the social security number.
        date_of_birth: Date of birth in YYYY-MM-DD format.
    """
    problems: List[str] = []

    if not full_name or len(full_name.strip()) < 3:
        problems.append("full_name")
    if not re.fullmatch(r"\d{4}", (ssn_last_four or "").strip()):
        problems.append("ssn_last_four")

    try:
        born = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        if born >= date.today():
            problems.append("date_of_birth")
    except (TypeError, ValueError):
        problems.append("date_of_birth")

    verified = not problems
    _set(context, "identity_verified", verified)

    return ToolResult(
        llm_response={
            "ok": True,
            "verified": verified,
            "invalid_fields": problems,
            "hint": (
                "Re-ask only for the invalid fields. SSN needs exactly four digits and "
                "the date of birth needs YYYY-MM-DD."
                if problems
                else "Identity checks out — a credit score can now be pulled."
            ),
        }
    )


@tool(description="Pull the customer's credit score after identity has been validated.")
async def get_credit_score(full_name: str = "", context: ToolContext = None) -> ToolResult:
    """Return a deterministic demo credit score.

    Args:
        full_name: Name to score, defaults to the customer in memory.
    """
    name = (full_name or _username(context)).strip()
    key = name.lower()

    if key in SEEDED_CREDIT_SCORES:
        score = SEEDED_CREDIT_SCORES[key]
    else:
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        score = 680 + int(digest, 16) % 71

    if score >= 740:
        band = "very good"
    elif score >= 700:
        band = "good"
    else:
        band = "fair"

    _set(context, "credit_score", score)
    _set(context, "credit_band", band)

    return ToolResult(
        llm_response={
            "ok": True,
            "full_name": name,
            "credit_score": score,
            "band": band,
            "scale": "300 to 850",
            "note": "Demo score generated locally — not a real credit bureau result.",
        }
    )


@tool(description="Work out what monthly car payment the customer can afford, including existing loans.")
async def calculate_affordability(
    monthly_income: float,
    monthly_expenses: float = 0.0,
    down_payment: float = 0.0,
    context: ToolContext = None,
) -> ToolResult:
    """Debt-to-income based affordability estimate.

    Args:
        monthly_income: Gross monthly income.
        monthly_expenses: Regular monthly outgoings excluding loan repayments.
        down_payment: Cash the customer can put down up front.
    """
    income = max(float(monthly_income), 0.0)
    if income == 0:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "income_required",
                "hint": "Ask the customer for their gross monthly income.",
            }
        )

    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    rows = (
        db.run_query(
            "SELECT monthly_payment FROM loans WHERE user_id = ?", (user_id,), one_record=False
        )
        if user_id is not None
        else []
    )
    existing_loan_payments = round(sum(float(row[0]) for row in rows or []), 2)

    expenses = max(float(monthly_expenses), 0.0)
    # Lenders here cap total debt service at 36% of gross income, and the payment
    # still has to fit inside what is actually left over each month.
    remaining_debt_capacity = income * 0.36 - existing_loan_payments
    disposable = income - expenses - existing_loan_payments
    affordable_payment = round(max(min(remaining_debt_capacity, disposable), 0.0), 2)

    current_dti = round((existing_loan_payments / income) * 100, 1)
    projected_dti = round(((existing_loan_payments + affordable_payment) / income) * 100, 1)

    rate = MockFinancingAPI.get_rate(DEFAULT_TERM_MONTHS)
    monthly_rate = rate / 100 / 12
    growth = (1 + monthly_rate) ** DEFAULT_TERM_MONTHS
    max_loan = round(affordable_payment * (growth - 1) / (monthly_rate * growth), 2)
    max_car_price = round(max_loan + max(float(down_payment), 0.0), 2)

    _set(context, "affordable_payment", affordable_payment)
    _set(context, "max_car_price", max_car_price)

    return ToolResult(
        llm_response={
            "ok": True,
            "monthly_income": round(income, 2),
            "monthly_expenses": round(expenses, 2),
            "existing_loan_payments": existing_loan_payments,
            "affordable_monthly_payment": affordable_payment,
            "current_dti_percent": current_dti,
            "projected_dti_percent": projected_dti,
            "max_loan_amount": max_loan,
            "max_car_price": max_car_price,
            "assumptions": f"{DEFAULT_TERM_MONTHS} month term at {rate}% APR, debt service capped at 36% of income.",
        }
    )


@tool(description="List the customer's existing loans and their monthly repayments.")
async def list_existing_loans(context: ToolContext = None) -> ToolResult:
    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    rows = db.run_query(
        """
        SELECT lender, purpose, principal, monthly_payment, remaining_months, interest_rate
        FROM loans WHERE user_id = ?
        """,
        (user_id,),
        one_record=False,
    )
    loans = [
        {
            "lender": lender,
            "purpose": purpose,
            "principal": float(principal),
            "monthly_payment": float(monthly_payment),
            "remaining_months": int(remaining_months),
            "interest_rate": float(interest_rate),
        }
        for lender, purpose, principal, monthly_payment, remaining_months, interest_rate in rows or []
    ]
    total = round(sum(loan["monthly_payment"] for loan in loans), 2)
    _set(context, "existing_loan_payments", total)

    return ToolResult(
        llm_response={
            "ok": True,
            "loans": loans,
            "loan_count": len(loans),
            "total_monthly_payments": total,
        }
    )


@tool(description="Calculate car finance options: monthly payment, rate, and total interest per term.")
async def calculate_financing(
    car_price: float = 0.0,
    down_payment: float = 0.0,
    term_months: int = 0,
    context: ToolContext = None,
) -> ToolResult:
    """Quote financing for a car.

    Args:
        car_price: Price of the car, 0 to use the car already in memory.
        down_payment: Cash up front, 0 to suggest using savings.
        term_months: Preferred term (36, 48, or 60), 0 to quote every term.
    """
    price = float(car_price) if car_price else float(_memory_value(context, "car_price") or 0.0)
    if not price:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "car_price_required",
                "hint": "Ask which car they want to finance, or reserve one first.",
            }
        )

    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    savings_row = (
        db.run_query(
            "SELECT balance FROM accounts WHERE user_id = ? AND type = 'savings'",
            (user_id,),
            one_record=True,
        )
        if user_id is not None
        else None
    )
    savings_balance = float(savings_row[0]) if savings_row else 0.0

    deposit = float(down_payment)
    if deposit <= 0 and savings_balance:
        # Suggest a deposit the customer can actually cover from savings.
        deposit = round(min(savings_balance * 0.5, price * 0.2), 2)

    if term_months:
        quotes = [MockFinancingAPI.quote(price, deposit, int(term_months))]
    else:
        quotes = MockFinancingAPI.quote_all_terms(price, deposit)

    _set(context, "down_payment", deposit)
    _set(context, "financing_quoted", True)
    if len(quotes) == 1:
        _set(context, "monthly_payment", quotes[0]["monthly_payment"])
        _set(context, "term_months", quotes[0]["term_months"])

    return ToolResult(
        llm_response={
            "ok": True,
            "car_model": _memory_value(context, "car_model") or "",
            "car_price": round(price, 2),
            "down_payment": round(deposit, 2),
            "savings_balance": savings_balance,
            "quotes": quotes,
            "note": "Illustrative demo figures — not a binding finance offer.",
        }
    )


# ---------------------------------------------------------------------------
# Human handoff
# ---------------------------------------------------------------------------


@tool(description="Create a handoff ticket so a Rasa Motors sales specialist can take over.")
async def create_handoff_ticket(reason: str, context: ToolContext = None) -> ToolResult:
    """Create a handoff ticket.

    Args:
        reason: Why the customer wants a human specialist.
    """
    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    ticket_id = f"HO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    db.cursor.execute(
        "INSERT INTO handoff_tickets (user_id, ticket_id, reason, status) VALUES (?, ?, ?, 'open')",
        (user_id, ticket_id, reason),
    )
    db.commit()

    _set(context, "handoff_created", True)
    _set(context, "handoff_ticket_id", ticket_id)

    return ToolResult(
        llm_response={
            "ok": True,
            "ticket_id": ticket_id,
            "reason": reason,
            "eta_minutes": 5,
        }
    )
