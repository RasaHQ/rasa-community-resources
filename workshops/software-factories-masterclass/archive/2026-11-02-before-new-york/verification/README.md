# Verification scope

These logs use synthetic or replay data and no live provider credentials. They are not voice or paid API acceptance. The full suite is not green: three socket-control failures and one process teardown error remain on this host. Targeted launcher tests passed independently. Do not omit the combined-suite failure when describing readiness.

The source integration's output uses an injected provider; its ACCEPT_OFFLINE label does not mean live acceptance. The hook/conversation logs exercise the real Mantle engine with scripted model replies.

Slide screenshots were visually reviewed but are not included as runtime dependencies. The PDF is in slides/masterclass-slides.pdf.
