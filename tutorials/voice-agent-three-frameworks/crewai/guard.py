# concern: refill-guard
"""Application-side confirmation checks; The tool coroutine waits for the next caller turn."""
import re
from cedar_clinic import refills

_AFFIRM = re.compile(r"^(yes|yeah|yep|yup|sure|ok|okay|fine|alright|all right|correct|right|absolutely|definitely|please( do| send)?|go ahead|that's (right|correct|the one|it)|that is (right|correct)|send it|do it)\b")
_NEGATE = re.compile(r"\b(no|nope|not|don't|dont|do not|wait|cancel|stop|instead|wrong|hold on|never mind)\b")
_LATER = re.compile(r"\b(don't send|do not send|not that|wait|cancel|instead|wrong|hold on|never mind)\b")
_NAMES = sorted({str(m['name']).lower() for m in refills.load_data()['medications'].values()})


def caller_said_yes(answer, label):
    """The same fixed answer rule as the historical Strands baseline."""
    text = str(answer or '').lower().replace('’', "'").strip()
    first = re.split(r'[.,!?;]', text, maxsplit=1)[0].strip()
    return bool(_AFFIRM.search(first) and not _NEGATE.search(first) and not _LATER.search(text)
                and not any(re.search(rf'\b{re.escape(name)}\b', text) and name not in label.lower()
                            for name in _NAMES))
