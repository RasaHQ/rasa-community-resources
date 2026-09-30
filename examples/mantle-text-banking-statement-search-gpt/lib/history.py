"""Northgate Bank transaction search and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the three request rules of the casebook contract for
``banking-statement-search`` (vendored as ``lib/fixtures/case-contract.json``)
when a search result is issued:

- ``date_range_confirmed``: the period resolves to exactly one range of dates,
  and every month, year, day and relative phrase in it ("last year", "last
  month") comes from the caller's own messages in this conversation. A month
  with no year the caller said is ambiguous: "March" on 2 April could be March
  2026 or March 2025, so the tool asks instead of picking one.
- ``posting_status_explicit``: which transactions to include (posted, pending
  or both) comes from the caller's own words. When they have not said, the
  tool asks the contract's question.
- ``result_scope_complete``: every page the history source holds for the
  query was read, and none came back partial. Until then the result is
  ``partial``: it lists what was read, gives no period total and carries a
  continuation, as the contract's recovery says.

The model supplies the caller's words for the period, the statuses, an
account and a merchant, and a search reference to continue. It never supplies
a fact, a date range it made up, a customer id or a total. A fact that is not
exactly ``True`` fails its rule, as in the lab's ``evaluate``.

Dates are the transaction's own date in the bank's timezone (Eastern time),
not the UTC timestamp's date, and a range never reaches past the fixture's
clock. A search result is never a statement: statements run on each account's
own cycle and come from ``get_statement``.

The organisation guard runs at import and is an allowlist: the fixture must
name the casebook contract's own fictional bank, marked fictional.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "northgate_history.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5). Every value a tool writes to memory
# is one short field and must fit; tests/test_guard.py checks every combination.
MEMORY_VALUE_LIMIT = 100

# The search tools send the customer the search receipt themselves through
# ToolContext.send, so the reference, range, statuses and completeness reach
# the customer whatever the model does next (the silent complete_skill found in
# the transfer, returns and claim builds). The `receipt-in-result-only` variant
# sets this to False.
TOOL_SENDS_RECEIPT = True

# Most transactions one tool result lists for the model.
MAX_LISTED = 40

ORGANISATION_KEYS = ("organisation", "bank", "institution", "issuer")


class FictionalOrganisationError(RuntimeError):
    """The fixture does not describe the casebook's fictional organisation."""


def _walk(value: Any):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key, inner
            yield from _walk(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _walk(inner)


def allowed_organisations(contract: dict) -> frozenset[str]:
    """The only organisation names the fixture may use: the contract's own."""
    return frozenset({contract["organisation"]})


def assert_fictional(data: dict, contract: dict) -> None:
    """Refuse fixture data whose organisation is not the casebook's fictional bank.

    An allowlist, not a list of real names: every organisation field must read
    ``<allowed name> (fictional ...)``. Real institution names are also caught
    repository-wide by scripts/lint_repo.py.
    """
    allowed = allowed_organisations(contract)
    found = [(k, v) for k, v in _walk(data) if k in ORGANISATION_KEYS]
    if not any(k == "organisation" for k, _ in found):
        raise FictionalOrganisationError("the fixture must name its organisation")
    for key, value in found:
        text = str(value or "")
        name, _, rest = text.partition(" (")
        if name not in allowed:
            raise FictionalOrganisationError(f"{key} {name!r} is not the casebook's organisation {sorted(allowed)}")
        if not rest.lower().startswith("fictional"):
            raise FictionalOrganisationError(f"{key} must be marked '(fictional ...)': {text!r}")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA, _CONTRACT)

ORGANISATION = _DATA["organisation"].split(" (")[0]
SESSION_CUSTOMER_ID = _DATA["session_customer_id"]
TZ = ZoneInfo(_DATA["timezone"])
TZ_LABEL = _DATA["timezone_label"]
AS_OF = datetime.fromisoformat(_DATA["as_of"])
TODAY = AS_OF.astimezone(TZ).date()
OWNER = _CONTRACT["owner"]

# ----------------------------------------------------------------------------
# Wording that presents a result set as complete: a period total, "that's all",
# "the full list". The output guard in hooks.py and case-build/case_metric.py
# apply it while a search is partial; the spec's `complete_claim` metric counts
# it in every bot sentence. tests/test_guard.py keeps the copies identical.
# ----------------------------------------------------------------------------

COMPLETE_CLAIM_PATTERN = (
    r"\b(?:in total|a total of|(?:your|the)\s+(?:\w+\s+){0,2}total\s+(?:is|was|comes? to|came to|of)"
    r"|total(?:s|led|ling|ing)?\s+(?:of\s+)?\$|altogether|in all\b|all told"
    r"|that'?s (?:all|everything|the (?:full|complete|whole))"
    r"|(?:the|a|your) (?:full|complete|whole|entire) (?:list|total|picture|set|history)"
    r"|(?:those|these) are all\b|here are all\b|all (?:of )?(?:your|the) (?:\w+ ){0,3}transactions"
    r"|you (?:spent|paid) \$[\d,]+(?:\.\d\d)?)"
)
COMPLETE_HEDGE_PATTERN = (
    r"\b(?:so far|shown|partial|partially|incomplete|not|isn't|aren't|wasn't|no|first|only|until|once|when|after"
    r"|if|at least|yet|more|remaining|page|pages|continue|continuing|can't|cannot|unable|without)\b|n't\b"
)
# A search total described as a statement figure.
STATEMENT_CLAIM_PATTERN = r"\b(?:statement (?:balance|total|amount)|closing balance|statement shows)"
STATEMENT_HEDGE_PATTERN = r"\b(?:not|isn't|no|never|differ|different|separate|rather than|instead|unlike)\b|n't\b"

_COMPLETE_RE = re.compile(COMPLETE_CLAIM_PATTERN, re.IGNORECASE)
_COMPLETE_HEDGE_RE = re.compile(COMPLETE_HEDGE_PATTERN, re.IGNORECASE)
_STATEMENT_RE = re.compile(STATEMENT_CLAIM_PATTERN, re.IGNORECASE)
_STATEMENT_HEDGE_RE = re.compile(STATEMENT_HEDGE_PATTERN, re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_AMOUNT_RE = re.compile(r"\$\s?([\d,]+\.\d\d)")


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_RE.split(text or "") if s.strip()]


def complete_claims(text: str) -> list[str]:
    """Phrases in *text* that present a result set as complete, sentence by sentence."""
    found = []
    for sentence in _sentences(text):
        if sentence.rstrip().endswith("?"):
            continue  # a question claims nothing
        for match in _COMPLETE_RE.finditer(sentence):
            if not _COMPLETE_HEDGE_RE.search(sentence[: match.start()]):
                found.append(match.group(0))
    return found


def statement_claims(text: str, totals: Iterable[str]) -> list[str]:
    """Sentences that call one of the given search totals a statement figure."""
    wanted = {t.replace("$", "").replace(",", "") for t in totals if t}
    found = []
    for sentence in _sentences(text):
        amounts = {a.replace(",", "") for a in _AMOUNT_RE.findall(sentence)}
        if not amounts & wanted:
            continue
        for match in _STATEMENT_RE.finditer(sentence):
            if not _STATEMENT_HEDGE_RE.search(sentence):
                found.append(sentence.strip())
                break
    return found


# ----------------------------------------------------------------------------
# Contract
# ----------------------------------------------------------------------------


def load_contract() -> dict:
    return json.loads(json.dumps(_CONTRACT))


def load_data() -> dict:
    return json.loads(json.dumps(_DATA))


def request_rules(contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == "request"]


def evaluate(facts: dict, contract: Optional[dict] = None) -> Optional[str]:
    """First failing request rule's reason, or None. Exactly ``True`` passes."""
    for rule in request_rules(contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8].upper()


def money(value: Decimal) -> str:
    return f"${abs(value):,.2f}"


def normalise_ref(value: Any) -> str:
    return re.sub(r"[^A-Z0-9-]", "", str(value or "").strip().upper())


def local_date(stamp: str) -> date:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(TZ).date()


def day_label(d: date) -> str:
    return f"{d.day} {calendar.month_name[d.month]} {d.year}"


def range_label(start: date, end: date) -> str:
    if start == end:
        return day_label(start)
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}-{end.day} {calendar.month_name[start.month]} {start.year}"
    if start.year == end.year:
        return f"{start.day} {calendar.month_name[start.month]} - {day_label(end)}"
    return f"{day_label(start)} - {day_label(end)}"


def short_range(start: date, end: date) -> str:
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}-{end.day} {calendar.month_abbr[start.month]} {start.year}"
    return f"{start.isoformat()} to {end.isoformat()}"


# ----------------------------------------------------------------------------
# Periods: resolving the caller's words, and checking they are the caller's
# ----------------------------------------------------------------------------

_MONTH_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b"
)
_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
_MONTHS["sept"] = 9
_YEAR_RE = re.compile(r"\b(20\d\d)\b")
_ISO_RE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_NUMERIC_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}\b")
# A day of the month: not part of an amount ("$1,450.00") or a longer number.
_DAY_RE = re.compile(r"(?<![\d$.,/])\b([1-9]|[12]\d|3[01])\b(?!\d|[.,/]\d)")
_SEPARATOR_RE = re.compile(r"\b(?:to|through|thru|until|till|and)\b|-")
_REL_YEAR = (
    (re.compile(r"\b(?:last|previous|past|prior) year\b|\ba year ago\b|\byear before\b"), -1),
    (re.compile(r"\bthis year\b|\bcurrent year\b"), 0),
)
_REL_MONTH = (
    (re.compile(r"\b(?:last|previous|past|prior) month\b|\ba month ago\b"), -1),
    (re.compile(r"\bthis month\b|\bcurrent month\b|\bmonth to date\b"), 0),
)


def _clean(text: Any) -> str:
    text = str(text or "").lower().replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)\b", r"\1", text)


def _month_shift(today: date, delta: int) -> tuple[int, int]:
    index = today.year * 12 + (today.month - 1) + delta
    return index // 12, index % 12 + 1


def _rel(patterns, text: str) -> Optional[int]:
    for pattern, value in patterns:
        if pattern.search(text):
            return value
    return None


def _month_end(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _unresolved(detail: str, **extra: Any) -> dict:
    return {"status": "unresolved", "detail": detail, **extra}


def _month_tokens(text: str) -> list[tuple[int, int, int]]:
    return [(m.start(), _MONTHS[m.group(1)], m.end()) for m in _MONTH_RE.finditer(text)]


def _day_tokens(text: str) -> list[tuple[int, int]]:
    blanked = _YEAR_RE.sub(lambda m: " " * len(m.group(0)), text)
    return [(m.start(), int(m.group(1))) for m in _DAY_RE.finditer(blanked)]


def resolve_period(words: Any, today: date = TODAY) -> dict:
    """Resolve a period in the caller's words to one inclusive range of local dates.

    Returns status ``resolved`` (start, end, label), ``ambiguous`` (a month or
    day with no year; candidates listed), or ``unresolved``.
    """
    text = _clean(words)
    if _NUMERIC_DATE_RE.search(text):
        return _unresolved("numeric_date")
    isos = []
    for y, m, d in _ISO_RE.findall(text):
        try:
            isos.append(date(int(y), int(m), int(d)))
        except ValueError:
            return _unresolved("invalid_date")
    text = _ISO_RE.sub(lambda m: " " * len(m.group(0)), text)
    rel_year = _rel(_REL_YEAR, text)
    rel_month = _rel(_REL_MONTH, text)
    months = _month_tokens(text)
    years = [(m.start(), int(m.group(1))) for m in _YEAR_RE.finditer(text)]
    days = _day_tokens(text)

    if isos:
        if months or days:
            return _unresolved("mixed_formats")
        start, end = (isos[0], isos[0]) if len(isos) == 1 else (min(isos[:2]), max(isos[:2]))
    elif not months:
        if rel_month is not None and not years:
            y, m = _month_shift(today, rel_month)
            start, end = date(y, m, 1), date(y, m, _month_end(y, m))
        elif (years or rel_year is not None) and not days:
            if len(years) > 1:
                return _unresolved("several_years")
            y = years[0][1] if years else today.year + rel_year
            start, end = date(y, 1, 1), date(y, 12, 31)
        else:
            return _unresolved("no_period")
    else:
        if len(months) > 2:
            return _unresolved("too_many_months")
        if len(years) == len(months):
            ys = [y for _, y in years]
        elif len(years) == 1 or (not years and rel_year is not None):
            y = years[0][1] if years else today.year + rel_year
            ys = [y] * len(months)
            if len(months) == 2 and months[0][1] > months[1][1]:
                ys[0] -= 1  # "December to February 2026"
        elif not years:
            return _ambiguous_year(text, months, days, today)
        else:
            return _unresolved("years_do_not_match_months")
        try:
            start, end = _span(text, months, ys, days)
        except ValueError:
            return _unresolved("invalid_date")
    if start > end:
        return _unresolved("start_after_end")
    if start > today:
        return _unresolved("future", start=start.isoformat())
    to_date = end > today
    end = min(end, today)
    label = range_label(start, end) + (" (to date)" if to_date else "")
    return {"status": "resolved", "start": start.isoformat(), "end": end.isoformat(), "label": label}


def _span(text: str, months, years, days) -> tuple[date, date]:
    """months: [(start, month, end)]; days: [(position, day)]. Inclusive local dates."""
    if len(months) == 1:
        (_, m, _), y = months[0], years[0]
        ds = sorted(d for _, d in days)
        if not ds:
            return date(y, m, 1), date(y, m, _month_end(y, m))
        return date(y, m, ds[0]), date(y, m, ds[-1])
    (_, m1, e1), (s2, m2, _) = months
    # Days before the separator between the two months belong to the first:
    # "3 March to 2 April", "March 3 to April 2".
    sep = _SEPARATOR_RE.search(text, e1, s2)
    split = sep.start() if sep else s2
    d1 = [d for p, d in days if p < split]
    d2 = [d for p, d in days if p >= split]
    start = date(years[0], m1, d1[0] if d1 else 1)
    end = date(years[1], m2, d2[-1] if d2 else _month_end(years[1], m2))
    return start, end


def _ambiguous_year(text: str, months, days, today: date) -> dict:
    m = months[0][1]
    latest = today.year if m <= today.month else today.year - 1
    candidates = []
    for y in (latest, latest - 1):
        ys = [y] * len(months)
        if len(months) == 2 and months[0][1] > months[1][1]:
            ys[0] -= 1
        try:
            start, end = _span(text, months, ys, days)
        except ValueError:
            continue
        if start > today:
            continue
        to_date = end > today
        candidates.append(range_label(start, min(end, today)) + (" (to date)" if to_date else ""))
    return {"status": "ambiguous", "detail": "no_year", "candidates": candidates}


def _caller_tokens(caller_texts: Iterable[str], today: date) -> dict:
    """What the caller has said about dates in this conversation."""
    text = " \n ".join(_clean(t) for t in caller_texts)
    months = {_MONTHS[m.group(1)] for m in _MONTH_RE.finditer(text)}
    years = {int(y) for y in _YEAR_RE.findall(text)}
    days = {d for _, d in _day_tokens(_ISO_RE.sub(" ", text))}
    for y, m, d in _ISO_RE.findall(text):
        years.add(int(y))
        months.add(int(m))
        days.add(int(d))
    rel_years = {value for pattern, value in _REL_YEAR if pattern.search(text)}
    rel_months = {value for pattern, value in _REL_MONTH if pattern.search(text)}
    for value in rel_years:
        years.add(today.year + value)
    for value in rel_months:
        y, m = _month_shift(today, value)
        years.add(y)
        months.add(m)
    return {"months": months, "years": years, "days": days, "rel_years": rel_years, "rel_months": rel_months}


def ungrounded_period_words(period: Any, caller_texts: Iterable[str], today: date = TODAY) -> list[str]:
    """Parts of *period* the caller never said: a month, a year, a day or a relative phrase.

    A year or month implied by what the caller said counts as said ("last year"
    grounds 2025; "last month" grounds March 2026).
    """
    said = _caller_tokens(caller_texts, today)
    text = _clean(period)
    missing = []
    for y, m, d in _ISO_RE.findall(text):
        if int(y) not in said["years"]:
            missing.append(y)
        if int(m) not in said["months"]:
            missing.append(calendar.month_name[int(m)])
        if int(d) not in said["days"] and not (int(d) == 1 or int(d) == _month_end(int(y), int(m))):
            missing.append(f"day {int(d)}")
    stripped = _ISO_RE.sub(" ", text)
    for m in _MONTH_RE.finditer(stripped):
        if _MONTHS[m.group(1)] not in said["months"]:
            missing.append(calendar.month_name[_MONTHS[m.group(1)]])
    for y in _YEAR_RE.findall(stripped):
        if int(y) not in said["years"]:
            missing.append(y)
    for _, d in _day_tokens(stripped):
        if d not in said["days"]:
            missing.append(f"day {d}")
    for pattern, value in _REL_YEAR:
        if pattern.search(stripped) and value not in said["rel_years"] and (today.year + value) not in said["years"]:
            missing.append(pattern.search(stripped).group(0))
    for pattern, value in _REL_MONTH:
        if pattern.search(stripped) and value not in said["rel_months"]:
            missing.append(pattern.search(stripped).group(0))
    return missing


# ----------------------------------------------------------------------------
# Statuses
# ----------------------------------------------------------------------------

_PENDING_RE = re.compile(r"\b(?:pending|authori[sz](?:ed|ations?)|holds?|uncleared|not (?:yet )?posted)\b")
_POSTED_RE = re.compile(r"\b(?:posted|cleared|settled|gone through|went through|booked)\b")
_BOTH_RE = re.compile(
    r"\b(?:both|everything|all statuses|posted and pending|pending and posted|including (?:the )?pending"
    r"|include (?:the )?pending|plus (?:the )?pending|and (?:the )?pending|also (?:the )?pending"
    r"|pending (?:ones |items |transactions )?(?:too|as well)|with (?:the )?pending)\b"
)
_NO_PENDING_RE = re.compile(r"\b(?:no|not|without|exclude|excluding|except|skip|leave out)\s+(?:the\s+|any\s+)?pending")

STATUS_LABELS = {("posted",): "posted only", ("pending",): "pending only", ("pending", "posted"): "posted and pending"}
STATUS_PHRASES = {("posted",): "posted transactions only", ("pending",): "pending transactions only",
                  ("pending", "posted"): "posted and pending transactions"}


def resolve_statuses(words: Any) -> Optional[tuple[str, ...]]:
    """('posted',), ('pending',), ('pending', 'posted'), or None when the words do not say."""
    text = _clean(words)
    no_pending = bool(_NO_PENDING_RE.search(text))
    if _BOTH_RE.search(text) and not no_pending:
        return ("pending", "posted")
    pending = bool(_PENDING_RE.search(_NO_PENDING_RE.sub(" ", text)))
    posted = bool(_POSTED_RE.search(text))
    if pending and posted:
        return ("pending", "posted")
    if posted or no_pending:
        return ("posted",)
    if pending:
        return ("pending",)
    return None


def statuses_grounded(statuses: tuple[str, ...], caller_texts: Iterable[str]) -> bool:
    """Whether the caller's own messages support including exactly these statuses."""
    said = [s for s in (resolve_statuses(t) for t in caller_texts) if s]
    if not said:
        return False
    if statuses in said:
        return True
    mentioned = {status for s in said for status in s}
    return set(statuses) <= mentioned


# ----------------------------------------------------------------------------
# Accounts and merchants
# ----------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z]+")
_DIGITS_RE = re.compile(r"\d{4}")
_ALL_ACCOUNTS_RE = re.compile(r"\b(?:all|every|any|each)\b|\bboth accounts\b")
_STOP = {"the", "at", "from", "to", "in", "on", "my", "store", "shop", "and", "of", "for", "inc", "co"}


def _phrase(value: Any) -> str:
    return " ".join(_WORD_RE.findall(str(value or "").lower().replace("-", " ")))


def _contains(phrase: str, words: str) -> bool:
    return bool(words) and re.search(rf"\b{re.escape(words)}\b", phrase) is not None


def account_label(account: dict) -> str:
    return f"{account['name']} (account ending {account['last_four']})"


def accounts_of(customer_id: Optional[str]) -> dict[str, dict]:
    return {r: a for r, a in sorted(_DATA["accounts"].items()) if customer_id and a["customer_id"] == customer_id}


def resolve_accounts(customer_id: Optional[str], spoken: Any, allow_all: bool = True) -> dict:
    """The caller's account(s) by name, alias or last four digits; no account named means all of them."""
    owned = accounts_of(customer_id)
    phrase = _phrase(spoken)
    if allow_all and (not phrase or _ALL_ACCOUNTS_RE.search(phrase)):
        return {"status": "resolved", "account_refs": list(owned), "account": "all your accounts"}
    digits = set(_DIGITS_RE.findall(str(spoken or "")))
    by_digits = [r for r, a in owned.items() if a["last_four"] in digits]
    by_name = [r for r, a in owned.items() if _contains(phrase, _phrase(a["name"]))]
    if not by_name:
        by_name = [r for r, a in owned.items() if any(_contains(phrase, al) for al in a["aliases"])]
    matches = [r for r in by_digits if not by_name or r in by_name] if by_digits else by_name
    if len(matches) == 1:
        return {"status": "resolved", "account_refs": matches, "account": account_label(owned[matches[0]])}
    return {
        "status": "blocked",
        "reason": "account_not_resolved",
        "detail": "ambiguous" if len(matches) > 1 else "not_found",
        "candidates": [account_label(owned[r]) for r in (matches if len(matches) > 1 else owned)],
        "effects": 0,
        "next_step": "Ask which of the caller's accounts they mean, by name. Do not guess.",
    }


def merchant_words(merchant: Any) -> list[str]:
    return [w for w in _WORD_RE.findall(str(merchant or "").lower()) if w not in _STOP and len(w) >= 3]


def merchant_matches(merchant: Any, name: str) -> bool:
    words = merchant_words(merchant)
    return bool(words) and all(_contains(_phrase(name), w) for w in words)


# ----------------------------------------------------------------------------
# The history source: paged, as the core system serves it
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Query:
    customer_id: str
    account_refs: tuple[str, ...]
    start: date
    end: date
    statuses: tuple[str, ...]
    merchant: Optional[str]

    def key(self) -> str:
        return _digest(self.customer_id, self.account_refs, self.start, self.end, self.statuses, self.merchant or "")


def _matching(query: Query) -> list[dict]:
    rows = []
    for t in _DATA["transactions"]:
        if t["account_ref"] not in query.account_refs:
            continue
        if _DATA["accounts"][t["account_ref"]]["customer_id"] != query.customer_id:
            continue
        if t["status"] not in query.statuses:
            continue
        d = local_date(t["at"])
        if not (query.start <= d <= query.end):
            continue
        if query.merchant and not merchant_matches(query.merchant, t["merchant"]):
            continue
        rows.append(t)
    return sorted(rows, key=lambda t: (t["at"], t["id"]))


class HistorySource:
    """The paged transaction-history service for one conversation (fixture behaviour included)."""

    def __init__(self) -> None:
        cfg = _DATA["history_source"]
        self.page_size: int = cfg["page_size"]
        self.pages_per_call: int = cfg["pages_per_call"]
        self.archive_before = date.fromisoformat(cfg["archive_before"])
        self.archive_pages_per_call: int = cfg["archive_pages_per_call"]
        self.partial_rule: dict = cfg["partial_page_once"]
        self._timed_out: set[tuple[str, int]] = set()
        self.requests = 0

    def budget(self, query: Query) -> int:
        return self.archive_pages_per_call if query.start < self.archive_before else self.pages_per_call

    def page(self, query: Query, index: int) -> tuple[list[dict], bool, bool]:
        """One page: (items, page_complete, more_pages_after_this_one)."""
        self.requests += 1
        rows = _matching(query)
        begin = index * self.page_size
        items = rows[begin: begin + self.page_size]
        more = begin + self.page_size < len(rows)
        rule = self.partial_rule
        if (rule["account_ref"] in query.account_refs and index == rule["page"] and items
                and (query.key(), index) not in self._timed_out):
            self._timed_out.add((query.key(), index))
            return items[: rule["items_returned"]], False, True
        return items, True, more


# ----------------------------------------------------------------------------
# One conversation's searches
# ----------------------------------------------------------------------------


@dataclass
class Search:
    ref: str
    query: Query
    account_label: str
    merchant_label: Optional[str]
    range_label: str
    items: dict[str, dict] = field(default_factory=dict)
    next_page: int = 0
    complete: bool = False
    pages_read: int = 0
    why_partial: Optional[str] = None


class HistoryService:
    def __init__(self) -> None:
        self.source = HistorySource()
        self.searches: dict[str, Search] = {}
        self.seq = 0


_SERVICES: dict[str, HistoryService] = {}


def service_for(conversation_id: str) -> HistoryService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = HistoryService()
    return _SERVICES[conversation_id]


def session_profile(customer_id: str = SESSION_CUSTOMER_ID) -> dict:
    person = _DATA["customers"][customer_id]
    accounts = [f"{a['name']} {a['last_four']}" for a in accounts_of(customer_id).values()]
    return {"customer_id": customer_id, "first_name": person["first_name"], "account_names": "; ".join(accounts)}


def _read_pages(service: HistoryService, search: Search) -> None:
    budget = service.source.budget(search.query)
    for _ in range(budget):
        items, page_complete, more = service.source.page(search.query, search.next_page)
        search.pages_read += 1
        for item in items:
            search.items.setdefault(item["id"], item)
        if not page_complete:
            search.why_partial = "the history source returned a partial page"
            return  # re-read the same page next time
        search.next_page += 1
        if not more:
            search.complete = True
            search.why_partial = None
            return
    search.why_partial = (
        "the archive serves one page per request" if budget == service.source.archive_pages_per_call
        and search.query.start < service.source.archive_before else "more pages remain"
    )


def _statement_note(account_refs: tuple[str, ...]) -> str:
    cycles = []
    for ref in account_refs:
        issued = [s for s in _DATA["statements"] if s["account_ref"] == ref]
        if issued:
            s = issued[-1]
            cycles.append(f"{_DATA['accounts'][ref]['name']} statements run {date.fromisoformat(s['cycle_start']).day}"
                          f" to {date.fromisoformat(s['cycle_end']).day} of the month")
    return ("A search result, not a statement balance. " + "; ".join(cycles) + ". Use get_statement for a statement."
            if cycles else "A search result, not a statement balance.")


def _row(t: dict) -> dict:
    amount = Decimal(t["amount"])
    return {
        "id": t["id"],
        "date": local_date(t["at"]).isoformat(),
        "merchant": t["merchant"],
        "amount": money(amount),
        "direction": "credit" if amount > 0 else "debit",
        "status": t["status"],
        "account": _DATA["accounts"][t["account_ref"]]["last_four"],
    }


def search_result(search: Search, replay: bool = False) -> dict:
    q = search.query
    rows = sorted(search.items.values(), key=lambda t: (t["at"], t["id"]))
    facts = {"date_range_confirmed": True, "posting_status_explicit": True, "result_scope_complete": search.complete}
    reason = evaluate(facts)
    result: dict[str, Any] = {
        "status": "complete" if search.complete else "partial",
        "reason": reason or "all_pages_read",
        "search_ref": search.ref,
        "range": {"start": q.start.isoformat(), "end": q.end.isoformat(), "label": search.range_label,
                  "timezone": TZ_LABEL, "basis": "transaction date"},
        "statuses": list(q.statuses),
        "status_label": STATUS_LABELS[q.statuses],
        "account": search.account_label,
        "merchant_filter": search.merchant_label,
        "complete": search.complete,
        "pages_read": search.pages_read,
        "count": len(rows),
        "transactions": [_row(t) for t in rows[:MAX_LISTED]],
        "facts": facts,
        "effects": 1,
        "replay": replay,
        "not_a_statement": _statement_note(q.account_refs),
    }
    if len(rows) > MAX_LISTED:
        result["listed"] = f"first {MAX_LISTED} of {len(rows)}"
    if search.complete:
        amounts = [Decimal(t["amount"]) for t in rows]
        debits = sum((a for a in amounts if a < 0), Decimal("0"))
        credits = sum((a for a in amounts if a > 0), Decimal("0"))
        result.update(total_debits=money(debits), total_credits=money(credits))
        result["next_step"] = (
            "The customer has been sent this search's reference, range, statuses and completeness. Answer their "
            "question from these transactions (a list or the totals). It is a search result for this range and these "
            "statuses, not a statement balance."
        )
    else:
        result.update(total_debits=None, total_credits=None,
                      continuation={"search_ref": search.ref, "why": search.why_partial})
        result["next_step"] = (
            "Partial result: not every transaction in the range has been read. Say it is partial, give only the "
            "transactions shown, and give no total for the period. Offer to continue; call continue_search with "
            "this search_ref to read the rest."
        )
    return result


def _question(period_label: str, period_missing: bool, statuses_missing: bool, candidates: list[str]) -> list[str]:
    questions = []
    if candidates:
        questions.append("Which period do you mean: " + " or ".join(candidates) + "?")
    elif period_missing:
        questions.append("Which dates do you mean? Please give the month and year, or the first and last day.")
    if statuses_missing:
        questions.append(
            _CONTRACT["question"].replace("during March", f"during {period_label}" if period_label else "in that period")
        )
    return questions


def search_transactions(
    service: HistoryService,
    customer_id: Optional[str],
    caller_texts: Iterable[str],
    period: Any,
    statuses: Any,
    account: Any,
    merchant: Any,
    conversation_id: str,
) -> dict:
    """Issue one transaction-search result, or say which of the case's facts is missing."""
    caller_texts = [t for t in caller_texts if t]
    accounts = resolve_accounts(customer_id, account)
    if accounts["status"] != "resolved":
        return accounts

    resolved = resolve_period(period)
    missing_words = ungrounded_period_words(period, caller_texts) if resolved["status"] == "resolved" else []
    date_ok = resolved["status"] == "resolved" and not missing_words
    wanted = resolve_statuses(statuses)
    status_ok = wanted is not None and statuses_grounded(wanted, caller_texts)
    facts = {"date_range_confirmed": date_ok, "posting_status_explicit": status_ok}
    reason = evaluate({**facts, "result_scope_complete": True})
    if reason:
        candidates = resolved.get("candidates", []) if resolved["status"] == "ambiguous" else []
        label = resolved.get("label", "") if date_ok else ""
        detail = {}
        if not date_ok:
            detail["period"] = (
                {"detail": "not_in_caller_words", "unsaid": missing_words} if resolved["status"] == "resolved"
                else {k: v for k, v in resolved.items() if k != "status"}
            )
        if not status_ok:
            detail["statuses"] = "not_said" if wanted is None else "not_in_caller_words"
        return {
            "status": "blocked",
            "reason": reason,
            "facts": facts,
            "detail": detail,
            "questions": _question(label, not date_ok, not status_ok, candidates),
            "effects": 0,
            "next_step": (
                "Nothing was searched. Ask the caller the questions above in one message, in plain words. Do not pick a "
                "year, a date range or the statuses for them, and do not pass words they did not say. When they answer, "
                "call search_transactions again with their words."
            ),
        }

    merchant_text = " ".join(str(merchant or "").split())[:40] or None
    query = Query(
        customer_id=customer_id,
        account_refs=tuple(accounts["account_refs"]),
        start=date.fromisoformat(resolved["start"]),
        end=date.fromisoformat(resolved["end"]),
        statuses=wanted,
        merchant=merchant_text,
    )
    matched = sorted({t["merchant"] for t in _DATA["transactions"]
                      if t["account_ref"] in query.account_refs and merchant_text
                      and merchant_matches(merchant_text, t["merchant"])})
    service.seq += 1
    ref = f"NB-SRCH-{_digest(conversation_id, service.seq, query.key())}"
    search = Search(ref=ref, query=query, account_label=accounts["account"],
                    merchant_label=(matched[0] if len(matched) == 1 else merchant_text), range_label=resolved["label"])
    _read_pages(service, search)
    service.searches[ref] = search
    return search_result(search)


def continue_search(service: HistoryService, customer_id: Optional[str], search_ref: Any) -> dict:
    """Read the next pages of one earlier search. Same range, statuses, account and merchant; never new ones."""
    ref = normalise_ref(search_ref)
    search = service.searches.get(ref)
    if search is None or search.query.customer_id != customer_id:
        return {"status": "not_found", "search_ref": ref, "effects": 0,
                "next_step": ("No search with this reference in this conversation. For a different period, statuses, "
                              "account or merchant, call search_transactions.")}
    if search.complete:
        return search_result(search, replay=True)
    _read_pages(service, search)
    return search_result(search)


# ----------------------------------------------------------------------------
# Statements: certified, per billing cycle
# ----------------------------------------------------------------------------


def get_statement(customer_id: Optional[str], account: Any, month: Any) -> dict:
    """The certified statement whose cycle ends in the given month (or the latest issued one)."""
    accounts = resolve_accounts(customer_id, account, allow_all=False)
    if accounts["status"] != "resolved":
        return accounts
    ref = accounts["account_refs"][0]
    statements = [s for s in _DATA["statements"] if s["account_ref"] == ref]
    text = _clean(month)
    target = None
    found = _MONTH_RE.search(text)
    if found:
        m = _MONTHS[found.group(1)]
        years = _YEAR_RE.findall(text)
        y = int(years[0]) if years else (TODAY.year if m <= TODAY.month else TODAY.year - 1)
        target = (y, m)
    if target:
        chosen = [s for s in statements if (date.fromisoformat(s["cycle_end"]).year,
                                           date.fromisoformat(s["cycle_end"]).month) == target]
    else:
        chosen = [s for s in statements if s["issued_on"]][-1:]
    if not chosen:
        return {"status": "not_found", "account": accounts["account"], "effects": 0,
                "cycles_on_file": [f"{s['cycle_start']} to {s['cycle_end']}" for s in statements],
                "next_step": "No statement cycle ends in that month. Tell the caller which cycles exist."}
    s = chosen[0]
    base = {"account": accounts["account"], "cycle_start": s["cycle_start"], "cycle_end": s["cycle_end"], "effects": 0}
    if not s["issued_on"]:
        return {"status": "not_issued", **base,
                "next_step": (f"This cycle closes on {s['cycle_end']} and has no statement yet. A transaction search "
                              "for part of it is not a statement.")}
    return {
        "status": "issued",
        "statement_ref": f"NB-STM-{accounts_of(customer_id)[ref]['last_four']}-{s['cycle_end'].replace('-', '')}",
        **base,
        "issued_on": s["issued_on"],
        "closing_balance": money(Decimal(s["closing_balance"])),
        "certified": True,
        "next_step": ("A certified statement for this billing cycle, which is not a calendar month. Give the cycle "
                      "dates with the closing balance. A transaction-search total is never a statement balance."),
    }


# ----------------------------------------------------------------------------
# What the customer is sent, and what memory holds
# ----------------------------------------------------------------------------


def customer_receipt(tool: str, result: dict) -> Optional[str]:
    """The message a search tool sends the customer for a result they must see, or None."""
    if tool not in ("search_transactions", "continue_search") or result.get("status") not in ("complete", "partial"):
        return None
    merchant = f" at {result['merchant_filter']}" if result.get("merchant_filter") else ""
    phrase = STATUS_PHRASES[tuple(sorted(result["statuses"]))]
    head = (f"Search {result['search_ref']}: {phrase}{merchant}, {result['account']}, "
            f"{result['range']['label']} ({TZ_LABEL}, by transaction date).")
    if result["complete"]:
        return (f"{head} Complete: yes, all {result['count']} matching transactions read. Debits "
                f"{result['total_debits']}, credits {result['total_credits']}. This is a search result, not a "
                "statement balance.")
    return (f"{head} Complete: no. {result['count']} transactions read so far; "
            f"{result['continuation']['why']}. There is no total for the period until the search is complete.")


def memory_values(result: dict) -> dict[str, str]:
    """Skill memory after an issued search: one short field per value."""
    if result.get("status") not in ("complete", "partial"):
        return {}
    start, end = date.fromisoformat(result["range"]["start"]), date.fromisoformat(result["range"]["end"])
    account = result["account"].replace(" (account ending ", " ").rstrip(")")
    merchant = f", {result['merchant_filter'][:30]}" if result.get("merchant_filter") else ""
    return {
        "last_search_ref": result["search_ref"],
        "last_search_scope": f"{result['status_label']}, {short_range(start, end)}, {account}{merchant}",
        "last_search_complete": "yes" if result["complete"] else "no",
    }
