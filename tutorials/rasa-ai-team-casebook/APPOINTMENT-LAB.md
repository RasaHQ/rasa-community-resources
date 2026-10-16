# Rehearse replies when a technician booking changes

This source prototype gives you booking states to use when designing an
assistant's replies. The customer already has a Tuesday visit and is considering
a held Wednesday slot. Run each scenario, inspect which visit remains active,
and decide what the assistant has enough evidence to say.

The data is fictional. This is a small SQLite scheduling service, separate from
the generic boolean exercises in `casebook.py`. It stores bookings, temporary
holds and successful request receipts. You can inspect the writes that commit
together and the failure that rolls them back.

## Run the scenarios

Use an existing Python 3.11 or 3.12 interpreter. These exercises use only its
standard library; no environment installation is needed. From the repository
root, run:

```sh
cd tutorials/rasa-ai-team-casebook
python3 appointment_scenarios.py expiry
python3 appointment_scenarios.py lost-reply
python3 appointment_scenarios.py write-failure
```

Each command creates temporary synthetic data and prints the original booking,
what the caller observed, the result of looking up the original request key,
and the active bookings afterwards. Time is an explicit integer input; the
expiry scenario advances it to the hold's expiry without waiting.

Compare these three situations before writing a reply:

| Situation | What the caller saw | What the service records show |
| --- | --- | --- |
| The hold expires | `hold_expired` | Tuesday remains active; the exchange has no success receipt. |
| The success reply is lost | `no_reply_received` | Lookup returns the successful Wednesday booking; Tuesday has been released. |
| A write fails after releasing Tuesday inside the transaction | `service_error` | Rollback leaves Tuesday active; the exchange has no success receipt. |

In the lost-reply scenario, a missing reply does not tell you whether the visit
changed. Try writing an acknowledgement for the interval before lookup and a
completion message after lookup. Explain which record supports each statement.
For expiry, explain that Tuesday remains booked before offering a new choice.

## Check the transitions

From the same directory:

```sh
python3 -m unittest discover -s tests -p test_appointment_exchange.py -v
```

Expect nine tests and `OK`, with no skips. They cover expiry, revision and
requirement changes, another customer, rollback, durable lookup after reopening
the database, repeat requests and a conflicting reuse of the same key. An
exception, failed assertion or skipped test needs investigation before you use
the corresponding behavior in a conversation design.

## Where the example's assumptions end

The exchange is atomic because the bookings, hold and receipt share a single
SQLite transaction. The fault before commit is a Python exception that triggers
rollback; it is not a measured operating-system crash. The lost-reply test
reopens the database before inspecting the persisted receipt.

A real scheduling API might expose separate reserve and cancel operations.
Map its documented intermediate states and recovery procedure before promising
that the old visit survives. This prototype does not supply that external
service guarantee, authentication layer or a Rasa tool binding. Its purpose is
to give the design exercise concrete states rather than predeclared booleans.

Publication plan: this is source development for the held technician-booking
lesson. The existing manuscript still needs revision, independent source-intake
review and qualification before it can teach this exercise.
