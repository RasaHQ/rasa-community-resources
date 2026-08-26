"""Mock financing calculator for the Autono demo.

Stands in for a lender API: fixed advertised rates per term, standard
amortisation for the monthly payment. Deterministic so a live demo always
produces the same numbers.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Advertised annual percentage rate by term length in months.
RATES_BY_TERM: Dict[int, float] = {
    36: 4.5,
    48: 5.0,
    60: 5.5,
}

DEFAULT_TERM_MONTHS = 60


class MockFinancingAPI:
    """Deterministic stand-in for a dealer financing provider."""

    rates = RATES_BY_TERM

    @classmethod
    def available_terms(cls) -> List[int]:
        return sorted(cls.rates)

    @classmethod
    def get_rate(cls, term_months: int) -> float:
        """Advertised APR for a term, falling back to the nearest offered term."""
        if term_months in cls.rates:
            return cls.rates[term_months]
        nearest = min(cls.rates, key=lambda term: abs(term - term_months))
        return cls.rates[nearest]

    @classmethod
    def calculate_monthly_payment(
        cls, principal: float, term_months: int, annual_rate: float
    ) -> float:
        """Standard amortised payment for a fixed-rate loan."""
        principal = max(float(principal), 0.0)
        term_months = max(int(term_months), 1)
        if principal == 0:
            return 0.0

        monthly_rate = float(annual_rate) / 100.0 / 12.0
        if monthly_rate == 0:
            return round(principal / term_months, 2)

        growth = (1 + monthly_rate) ** term_months
        payment = principal * monthly_rate * growth / (growth - 1)
        return round(payment, 2)

    @classmethod
    def quote(
        cls, car_price: float, down_payment: float = 0.0, term_months: int = DEFAULT_TERM_MONTHS
    ) -> Dict[str, Any]:
        """Full quote for one term: rate, payment, and total interest."""
        car_price = max(float(car_price), 0.0)
        down_payment = min(max(float(down_payment), 0.0), car_price)
        principal = car_price - down_payment

        term = int(term_months)
        rate = cls.get_rate(term)
        monthly_payment = cls.calculate_monthly_payment(principal, term, rate)
        total_paid = round(monthly_payment * term, 2)

        return {
            "car_price": round(car_price, 2),
            "down_payment": round(down_payment, 2),
            "loan_amount": round(principal, 2),
            "term_months": term,
            "annual_rate": rate,
            "monthly_payment": monthly_payment,
            "total_paid": total_paid,
            "total_interest": round(total_paid - principal, 2),
        }

    @classmethod
    def quote_all_terms(
        cls, car_price: float, down_payment: float = 0.0
    ) -> List[Dict[str, Any]]:
        """One quote per advertised term, shortest first."""
        return [cls.quote(car_price, down_payment, term) for term in cls.available_terms()]
