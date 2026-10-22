# Chapter 5 ready folder

Use the [chapter](../../05-the-builder.md). This folder provides the baseline,
public task, protected tests and child runner, a scripted teaching builder,
and the existing factory with its confined Core Agents driver.

`factory_engine/` supplies the factory so this chapter can start alone.
To change the card, change the public task; the builder writes the code and
separate tests judge it. The offline path makes no provider request. Product
integration and restart are later steps.

The network-blocking protected check requires macOS sandbox-exec. Without it,
the gate reports that it could not run, with exit 2, before judging the attempt.
No credentials are needed for the scripted exercise after installation.
