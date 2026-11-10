# Chapter 5 ready folder

Use the [chapter](../../05-the-builder.md). This folder provides the baseline,
public task, protected tests and child runner, a scripted teaching builder,
and the existing factory with its confined Core Agents driver.

`factory_engine/` supplies the factory so this chapter can start alone.
To change the card, change the public task; the builder writes the code and
separate tests judge it. The offline path makes no provider request. Product
integration and restart are later steps.

The network-blocking protected check uses the pinned `acceptance/isolation.py`
helper: macOS `sandbox-exec`, or a Linux network namespace wrapper only after
the helper proves that it runs Python and blocks a connection that an
unwrapped control can make. A timeout never counts as a block. The task pins
the helper and both protected suites before any helper code is imported.
Without a verified wrapper, the gate reports that it could not run, with
exit 2, before judging an attempt or dispatching the builder.
No credentials are needed for the scripted exercise after installation.

The strict factory copies the helper beside its protected acceptance suite in
scratch, outside the candidate's allowed paths. The candidate still cannot
change the acceptance suite, its helper, or their trusted pins. The existing
Python 3.12/Core worker requirements and provider-call bounds are unchanged.

**Linux status: NOT YET QUALIFIED.** Run the offline readiness controls with
`python3 -B -m unittest test_readiness -v`. These check refusal and copy layout;
they do not prove a real good-ACCEPT/bad-REJECT pair or a provider-backed build.
Those require independent receiving in the supported worker. This chapter's
currency-card acceptance is not a router-command oracle. A workshop router
task needs its own independent checks. The separate factory example's LIVE
non-macOS refusal remains in place until its complete path is qualified.
