"""Deterministic queued displays: business value and presentation have separate clocks."""
from dataclasses import dataclass
import json

from localized_amount import Amount


@dataclass(frozen=True)
class Render:
    amount: Amount
    locale: str
    value_version: int
    locale_version: int


class Display:
    """A local UI fixture, not an agent runtime or a payment service."""

    def __init__(self):
        self.amount = Amount(100050, "EUR")
        self.locale = "en-US"
        self.value_version = 0
        self.locale_version = 0
        self.visible = None

    def edit_amount(self, minor):
        amount = Amount(minor, self.amount.currency)
        if amount != self.amount:
            self.amount = amount
            self.value_version += 1

    def change_locale(self, locale):
        self.amount.display(locale)  # Reject unsupported presentation before mutation.
        if locale != self.locale:
            self.locale = locale
            self.locale_version += 1

    def start(self):
        return Render(self.amount, self.locale, self.value_version, self.locale_version)

    def complete(self, job, guard):
        if guard not in {"value", "locale", "pair"}:
            raise ValueError("Choose value, locale or pair")
        value_matches = job.value_version == self.value_version
        locale_matches = job.locale_version == self.locale_version
        accept = {"value": value_matches, "locale": locale_matches,
                  "pair": value_matches and locale_matches}[guard]
        if accept:
            self.visible = {"minor": job.amount.minor, "currency": job.amount.currency,
                            "locale": job.locale, "text": job.amount.display(job.locale)}
        return accept

    def approve_value(self):
        # Fixture contract: approval binds amount/currency, not its display language.
        return (self.value_version, self.locale_version)

    def approval_valid(self, approval, *, coarse=False):
        return approval == (self.value_version, self.locale_version) if coarse else approval[0] == self.value_version


def history(guard):
    state = Display()
    before_both_changes = state.start()
    state.edit_amount(200050)
    after_amount_change = state.start()
    results = []
    for name, job in [("old_value_and_locale", before_both_changes),
                      ("new_value_old_locale", after_amount_change)]:
        if name == "new_value_old_locale":
            state.change_locale("de-DE")
        results.append({"job": name, "accepted": state.complete(job, guard),
                        "visible": state.visible, "required_minor": state.amount.minor,
                        "required_locale": state.locale})
    fresh = state.start()
    state.complete(fresh, guard)
    return {"completions": results, "fresh_display": state.visible,
            "canonical_minor": state.amount.minor, "preferred_locale": state.locale}


def demo():
    state = Display()
    approval = state.approve_value()
    state.change_locale("de-DE")
    locale_only = {"value_bound_approval": state.approval_valid(approval),
                   "coarse_approval": state.approval_valid(approval, coarse=True)}
    state.edit_amount(200050)
    return {"same_schedule": {g: history(g) for g in ["value", "locale", "pair"]},
            "locale_only_change": locale_only,
            "after_amount_change_approval": state.approval_valid(approval)}


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2, sort_keys=True))
