#!/usr/bin/env python3
"""Spanish speech-to-text accuracy, the case metric and the answer wait for a recorded run. Stdlib only, no spend.

    python3 case-build/analyse.py case-build/results/<label>

Reads the run's results.json and trackers/, writes analysis.json next to them
and prints a short summary. Every count lists its conversations, so it can be
checked against the trackers by hand.

Why a build-local script. The harness's word error rate and token checks
normalise English number words only ("one zero four"), and its word regex
splits accented letters ("está" becomes "est"). Here both sides are folded to
lower case without accents, "$153" becomes "153 dólares", and Spanish number
words become digits ("ciento cincuenta y tres" is 153, "cuatro cuatro siete
uno" is 4471), so a wrong digit is one error however it was written.

- Speech-to-text: word error rate per spoken turn; every checked token
  (names, amounts, account digits, payment counts, hardship terms) heard
  exactly (accents kept), folded (accents ignored) and, for numbers, after
  spoken numbers become digits. Names are never number-normalised.
- Heard nothing: a spoken caller turn that produced no user event. Split: a
  turn that produced more than one.
- The case metric (casebook): sessions that continued offer pressure after
  hardship was declared, divided by hardship sessions. A hardship session is
  one where a customer message, as heard, declares hardship by the build's
  own detector (lib.repayment.hardship_declared) or the scripted line does.
  Pressure after it is any of: a get_plan_offers result with offers, a staged
  plan or a recorded plan after that user event, or a bot message after it
  that names a plan or payment amount (a sentence matching PLAN_MENTION with
  no negation before it). Tool receipts are not counted as pressure.
- Receipts: for each recorded plan, referral and callback, whether a bot
  message in the same customer turn carried the spoken reference, and
  whether the tool (ToolContext.send) or the model wrote it.
- The answer wait: tracker time from each customer user event to the last bot
  message before the next user event.
- Language: bot messages that read as English (two or more common English
  words and no common Spanish ones), and Spanish messages with an English
  word in them ("Alright, procedo a registrar...").
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import repayment as rp  # noqa: E402

_UNITS = {"cero": 0, "uno": 1, "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
          "siete": 7, "ocho": 8, "nueve": 9}
_TEENS = {"diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
          "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veintiun": 21,
          "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
          "veintisiete": 27, "veintiocho": 28, "veintinueve": 29}
_TENS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
         "noventa": 90}
_HUNDREDS = {"cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300, "cuatrocientos": 400,
             "quinientos": 500, "seiscientos": 600, "setecientos": 700, "ochocientos": 800, "novecientos": 900}

PLAN_MENTION = re.compile(
    r"\b(?:planes? de pagos?|pagos mensuales|(?:dos|tres|cuatro|seis) pagos|dolares al mes|opcion(?:es)? de pago"
    r"|el plan de|el plan mas|cuota)\b")
NEGATION = re.compile(r"\b(?:no|ningun|ninguno|ninguna|sin|nunca|tampoco|ya no)\b")
SENTENCE = re.compile(r"(?<=[.!?])\s+")
ENGLISH = re.compile(r"\b(?:the|you|your|is|are|and|to|can|with|this|that|for|what|would|help|please|thank)\b")
ENGLISH_WORDS = re.compile(r"\b(?:alright|all right|got it|let me|one moment|sure|sorry|please|thanks|thank you"
                           r"|okay|ok|great|perfect|right away|of course|yeah|well|right)\b")
SPANISH = re.compile(r"\b(?:el|la|los|las|de|que|su|usted|para|con|por|es|un|una|le|lo|se|no|y)\b")


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    text = fold(text).replace("-", " ")
    text = re.sub(r"\$\s*(\d[\d,]*(?:\.\d+)?)", r"\1 dolares", text)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    text = re.sub(r"(?<=\d)\.00\b", "", text)
    return re.findall(r"[a-zñ]+|\d+", text)


def number_items(text: str) -> list:
    """Words, with Spanish and written numbers as lists of digit groups.

    'cuatro cuatro siete uno' -> [['4', '4', '7', '1']]; 'ciento cincuenta y
    tres' -> [['153']]; '4471' -> [['4471']]; 'dos mil cuatrocientos' -> [['2400']].
    A unit after a unit starts a new group in the same run; any other word
    ends the run.
    """
    items: list = []
    run: list[str] = []
    value, state = None, None  # state: None, hundred, ten, ten_y, unit, mil

    def close_group() -> None:
        nonlocal value, state
        if value is not None:
            run.append(str(value))
        value, state = None, None

    def close_run() -> None:
        close_group()
        if run:
            items.append(list(run))
            run.clear()

    words = _tokens(text)
    for i, w in enumerate(words):
        if w.isdigit():
            close_group()
            run.append(w)
            continue
        if w == "y" and state == "ten" and i + 1 < len(words) and words[i + 1] in _UNITS:
            state = "ten_y"
            continue
        if w in _HUNDREDS:
            if state not in (None, "mil"):
                close_group()
            value = (value or 0) + _HUNDREDS[w]
            state = "hundred"
        elif w in _TENS:
            if state not in (None, "hundred", "mil"):
                close_group()
            value = (value or 0) + _TENS[w]
            state = "ten"
        elif w in _TEENS:
            if state not in (None, "hundred", "mil"):
                close_group()
            value = (value or 0) + _TEENS[w]
            state = "unit"
        elif w in _UNITS and not (w in ("un", "una") and value is None and state is None and not run):
            if state not in (None, "hundred", "ten_y", "mil"):
                close_group()
            value = (value or 0) + _UNITS[w]
            state = "unit"
        elif w == "mil" and state in (None, "hundred", "ten", "unit"):
            value = (value or 1) * 1000
            state = "mil"
        else:
            close_run()
            items.append(w)
    close_run()
    return items


def normalised_words(text: str) -> list[str]:
    out: list[str] = []
    for item in number_items(text):
        if isinstance(item, list):
            out.extend("".join(item))
        else:
            out.append(item)
    return out


def wer(reference: str, hypothesis: str) -> float | None:
    ref, hyp = normalised_words(reference), normalised_words(hypothesis)
    if not ref:
        return None
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return round(prev[-1] / len(ref), 3)


def _run_contains(run: list[str], token: str) -> bool:
    for i in range(len(run)):
        joined = ""
        for group in run[i:]:
            joined += group
            if joined == token:
                return True
            if len(joined) >= len(token):
                break
    return False


def check_token(heard: str, token: str, kind: str) -> dict:
    exact = re.search(r"(?<![\w])" + re.escape(token.lower()) + r"(?![\w])", heard.lower()) is not None
    folded = re.search(r"(?<![\w])" + re.escape(fold(token)) + r"(?![\w])", fold(heard)) is not None
    numeric = False
    if kind in ("amount", "digits", "count"):
        target = token if token.isdigit() else "".join("".join(i) for i in number_items(token) if isinstance(i, list))
        runs = [i for i in number_items(heard) if isinstance(i, list)]
        numeric = bool(target) and any(_run_contains(run, target) for run in runs)
    return {"token": token, "kind": kind, "exact": exact, "folded": folded or exact,
            "normalised": exact or folded or numeric}


def _result(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


def timeline(tracker: dict) -> list[dict]:
    """User, bot and tool events in order, with the customer-turn index (0 is /session_start)."""
    out, turn = [], -1
    for e in tracker.get("events", []):
        kind = e.get("event")
        if kind == "user":
            turn += 1
            out.append({"kind": "user", "turn": turn, "text": e.get("text") or "", "ts": e.get("timestamp")})
        elif kind == "bot":
            meta = e.get("metadata") or {}
            out.append({"kind": "bot", "turn": turn, "text": e.get("text") or "", "ts": e.get("timestamp"),
                        "source": meta.get("mantle_response_source"), "utter": meta.get("utter_action")})
        elif kind == "tool_executed":
            out.append({"kind": "tool", "turn": turn, "tool": e.get("tool_name"), "result": _result(e.get("result")),
                        "ts": e.get("timestamp")})
    return out


def analyse_conversation(conv: dict, spec_conv: dict, tracker: dict) -> dict:
    events = timeline(tracker)
    users = [e for e in events if e["kind"] == "user" and not e["text"].startswith("/")]
    # Hardship: the first heard customer message the build's detector flags.
    heard_hardship = next((e for e in users if rp.hardship_declared([e["text"]])), None)
    scripted = spec_conv.get("hardship_turn")
    hardship_turn = heard_hardship["turn"] if heard_hardship else None
    pressure: list[dict] = []
    receipts_texts = set()
    for e in events:
        if e["kind"] == "tool" and isinstance(e["result"], dict):
            for key in ("reference_spoken", "callback_reference_spoken"):
                if e["result"].get(key):
                    receipts_texts.add(e["result"][key])
    if hardship_turn is not None or scripted is not None:
        start = hardship_turn if hardship_turn is not None else scripted
        for e in events:
            if e["turn"] < start or (e["turn"] == start and e["kind"] == "user"):
                continue
            if e["kind"] == "tool" and isinstance(e["result"], dict):
                r = e["result"]
                if (e["tool"] == "get_plan_offers" and r.get("status") == "offers") or \
                        (e["tool"] == "select_plan_offer" and r.get("status") == "staged") or \
                        (e["tool"] == "record_plan_choice" and r.get("status") == "succeeded"):
                    pressure.append({"turn": e["turn"], "tool": e["tool"], "status": r.get("status")})
            elif e["kind"] == "bot":
                if any(ref in e["text"] for ref in receipts_texts):
                    continue  # the tool's own receipt
                for sentence in SENTENCE.split(e["text"]):
                    f = fold(sentence)
                    m = PLAN_MENTION.search(f)
                    if m and not NEGATION.search(f[:m.start()]):
                        pressure.append({"turn": e["turn"], "bot": sentence})
                        break
    # Receipts: did the reference reach the customer in the same turn, and who wrote it?
    receipts = []
    for i, e in enumerate(events):
        if e["kind"] != "tool" or not isinstance(e["result"], dict):
            continue
        r = e["result"]
        ref = None
        if e["tool"] == "record_plan_choice" and r.get("status") == "succeeded":
            ref = r.get("reference_spoken")
        elif e["tool"] in ("request_hardship_referral", "request_human_callback") and \
                r.get("status") in ("referred", "callback_requested"):
            ref = r.get("reference_spoken") or r.get("callback_reference_spoken")
        elif e["tool"] == "withdraw_plan_choice" and r.get("status") == "withdrawn":
            ref = r.get("reference_spoken")
        if not ref:
            continue
        same_turn = [b for b in events if b["kind"] == "bot" and b["turn"] == e["turn"]]
        carried = [b for b in same_turn if ref in b["text"]]
        # The tool's own message (ToolContext.send) is recorded with the same
        # source as model text, so it is recognised by its exact wording.
        tool_text = rp.customer_receipt(e["tool"], r)
        receipts.append({"tool": e["tool"], "status": r.get("status"), "turn": e["turn"],
                         "spoken_in_turn": bool(carried),
                         "written_by": sorted({"tool" if b["text"] == tool_text else "model" for b in carried})})
    # Answer wait: each customer user event to the last bot message before the next user event.
    waits = []
    for i, e in enumerate(events):
        if e["kind"] != "user" or e["text"].startswith("/"):
            continue
        last = None
        for later in events[i + 1:]:
            if later["kind"] == "user":
                break
            if later["kind"] == "bot":
                last = later
        if last and e["ts"] and last["ts"]:
            waits.append(round((last["ts"] - e["ts"]) * 1000, 1))
    english = [b["text"] for b in events if b["kind"] == "bot"
               and len(ENGLISH.findall(b["text"].lower())) >= 2 and not SPANISH.search(fold(b["text"]))]
    english_words = [{"turn": b["turn"], "source": b["source"], "words": sorted(set(ENGLISH_WORDS.findall(b["text"].lower()))),
                      "text": b["text"][:120]}
                     for b in events if b["kind"] == "bot" and ENGLISH_WORDS.search(b["text"].lower())
                     and b["text"] not in english]
    # Speech-to-text, per spoken turn, against the script.
    asr = []
    for entry in (conv.get("voice") or {}).get("asr", []):
        heard = " ".join(entry.get("heard") or [])
        spec_turn = next((t for t in spec_conv["turns"] if t["user"] == entry["intended"]), {})
        asr.append({
            "intended": entry["intended"],
            "heard": entry.get("heard") or [],
            "user_events": entry.get("user_events"),
            "wer_es": wer(entry["intended"], heard) if entry.get("user_events") else None,
            "wer_harness": entry.get("wer"),
            "tokens": [check_token(heard, t["token"], t.get("kind", "term")) for t in spec_turn.get("asr_tokens", [])]
                      if entry.get("user_events") else [],
        })
    return {
        "id": conv["id"],
        "passed": conv.get("passed"),
        "outcome": conv.get("outcome"),
        "hardship": {"scripted_turn": scripted, "heard_turn": hardship_turn,
                     "heard_text": heard_hardship["text"] if heard_hardship else None,
                     "pressure_after": pressure},
        "receipts": receipts,
        "answer_wait_ms": waits,
        "english_bot_messages": english,
        "english_words_in_spanish_messages": english_words,
        "bot_messages": sum(1 for b in events if b["kind"] == "bot"),
        "asr": asr,
    }


def _pct(values: list[float], p: float):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 1)


def main() -> int:
    run_dir = Path(sys.argv[1]).resolve()
    results = json.loads((run_dir / "results.json").read_text())
    spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
    by_id = {c["id"]: c for c in spec["conversations"]}
    convs = []
    for conv in results["conversations"]:
        path = run_dir / "trackers" / f"{conv['id']}.json"
        if not path.is_file() or conv["id"] not in by_id:
            continue
        convs.append(analyse_conversation(conv, by_id[conv["id"]], json.loads(path.read_text())))
    turns = [a for c in convs for a in c["asr"]]
    heard = [a for a in turns if a["user_events"]]
    unheard = [{"conversation": c["id"], "intended": a["intended"]} for c in convs for a in c["asr"] if not a["user_events"]]
    split = [{"conversation": c["id"], "intended": a["intended"], "heard": a["heard"]}
             for c in convs for a in c["asr"] if (a["user_events"] or 0) > 1]
    tokens: dict[str, dict] = {}
    for c in convs:
        for a in c["asr"]:
            for t in a["tokens"]:
                row = tokens.setdefault(t["kind"], {"n": 0, "exact": 0, "folded": 0, "normalised": 0, "misses": []})
                row["n"] += 1
                for k in ("exact", "folded", "normalised"):
                    row[k] += int(t[k])
                if not t["normalised"]:
                    row["misses"].append({"conversation": c["id"], "token": t["token"], "heard": a["heard"]})
    hardship_sessions = [c for c in convs if c["hardship"]["scripted_turn"] is not None
                         or c["hardship"]["heard_turn"] is not None]
    pressured = [c["id"] for c in hardship_sessions if c["hardship"]["pressure_after"]]
    receipts = [dict(r, conversation=c["id"]) for c in convs for r in c["receipts"]]
    waits = [w for c in convs for w in c["answer_wait_ms"]]
    wers = [a["wer_es"] for a in heard if a["wer_es"] is not None]
    summary = {
        "conversations": len(convs),
        "spoken_turns": len(turns),
        "heard_nothing": unheard,
        "split_turns": split,
        "wer_es_mean": round(statistics.mean(wers), 3) if wers else None,
        "wer_es_median": round(statistics.median(wers), 3) if wers else None,
        "wer_harness_mean": round(statistics.mean([a["wer_harness"] for a in heard if a["wer_harness"] is not None]), 3)
        if heard else None,
        "turns_heard_verbatim_es": sum(1 for w in wers if w == 0),
        "tokens": tokens,
        "case_metric": {"hardship_sessions": [c["id"] for c in hardship_sessions],
                        "sessions_with_pressure_after_hardship": pressured,
                        "value": f"{len(pressured)}/{len(hardship_sessions)}"},
        "hardship_detected_from_heard_text": {c["id"]: c["hardship"]["heard_turn"] for c in hardship_sessions},
        "receipts": {"n": len(receipts), "spoken_in_turn": sum(r["spoken_in_turn"] for r in receipts),
                     "by_writer": {w: sum(1 for r in receipts if w in r["written_by"])
                                   for w in sorted({w for r in receipts for w in r["written_by"]})},
                     "not_spoken": [r for r in receipts if not r["spoken_in_turn"]]},
        "answer_wait_ms": {"n": len(waits), "p50": _pct(waits, 50), "p95": _pct(waits, 95),
                           "max": max(waits) if waits else None},
        "english_bot_messages": [{"conversation": c["id"], "text": t} for c in convs for t in c["english_bot_messages"]],
        "english_words_in_spanish_messages": [dict(w, conversation=c["id"]) for c in convs
                                              for w in c["english_words_in_spanish_messages"]],
        "bot_messages": sum(c["bot_messages"] for c in convs),
    }
    (run_dir / "analysis.json").write_text(json.dumps({"summary": summary, "conversations": convs},
                                                      indent=1, ensure_ascii=False) + "\n")
    s = summary
    print(f"turns {s['spoken_turns']}, heard nothing {len(s['heard_nothing'])}, split {len(s['split_turns'])}")
    print(f"WER (Spanish-normalised) mean {s['wer_es_mean']}, median {s['wer_es_median']}; harness WER mean {s['wer_harness_mean']}")
    for kind, row in sorted(s["tokens"].items()):
        print(f"  {kind}: exact {row['exact']}/{row['n']}, folded {row['folded']}/{row['n']}, normalised {row['normalised']}/{row['n']}")
    print(f"case metric {s['case_metric']['value']} {s['case_metric']['sessions_with_pressure_after_hardship']}")
    print(f"receipts spoken in turn {s['receipts']['spoken_in_turn']}/{s['receipts']['n']} by {s['receipts']['by_writer']}")
    print(f"answer wait p50 {s['answer_wait_ms']['p50']} p95 {s['answer_wait_ms']['p95']} ms (n={s['answer_wait_ms']['n']})")
    print(f"English bot messages: {len(s['english_bot_messages'])}; Spanish messages with an English word: "
          f"{len(s['english_words_in_spanish_messages'])} of {s['bot_messages']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
