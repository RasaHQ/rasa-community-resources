# Chapter 5 ready folder

sow: software-factories-masterclass-SOW-02

Use the [chapter](../../05-the-builder.md). This folder provides the baseline,
public task B, protected tests and child runner, a scripted teaching builder,
and the existing factory engine plus its confined Core Agents driver.
The engine is copied from PR133 at41738dd; task pack from PR130 at4346e25.
No live call, integration or product restart is represented by the offline control.
`factory_engine/` is the same factory code, bundled so this chapter can start alone.
Do not edit a bundled engine to change the card: change the public task.

The network-blocking protected check requires macOS sandbox-exec. No credentials
are needed for the scripted exercise after the pinned dependencies are installed.
