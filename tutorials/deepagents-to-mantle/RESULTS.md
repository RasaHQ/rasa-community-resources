# Limit the results your SQL tool returns

The shared SQL helper already limits row count and query work. A single row
can still hold a large text value, and a SQLite binary value is not a JSON
string. Check those properties before passing results to an agent.

This exercise uses a temporary local database. It does not download Chinook,
start an agent, install an SDK or make a model call. Use Python 3.12, the
version supported by this project's package. Check `python3 --version` first.
If it selects another version, check an existing `python3.12 --version` and use
`python3.12` in place of `python3` in every command below. Continue once your
selected interpreter reports Python 3.12. The source SHA and actual Python
and SQLite versions appear in each report.

## Compare the same inputs

From `tutorials/deepagents-to-mantle`, run:

```sh
python3 -B exercises/result_contract.py
```

To inspect the earlier helper from an existing repository checkout, export its
exact source. The export executes only when you pass it to the exercise; use
the trusted historical revision shown here.

```sh
exercise_dir=$(mktemp -d)
git show 8a4e14307b1def6d8b609732df7515ed7063ef8d:tutorials/deepagents-to-mantle/shared/database.py > "$exercise_dir/before.py"
python3 -B exercises/result_contract.py --source "$exercise_dir/before.py" > "$exercise_dir/before.json"
python3 -B exercises/result_contract.py > "$exercise_dir/after.json"
```

Inspect both reports. They omit cell contents, so the large-value case does
not flood your terminal. Both use the same queries and fresh database layout.

Read the saved reports with Python's JSON formatter:

```sh
python3 -m json.tool "$exercise_dir/before.json"
python3 -m json.tool "$exercise_dir/after.json"
```

Keep `sourceSha256` with each result to identify the helper that ran. Both
reports should have `databaseUnchanged: true`, and the ordinary scalar should
remain successful. Compare `status` and `reason` for each other named case
with the table below.

| Input | Earlier helper | Current result contract |
| --- | --- | --- |
| One integer | JSON result | JSON result |
| One text cell made from a 64 KiB binary value | One row, with a large JSON result | `sqlite_value_too_large` |
| An eight-byte binary value | Python bytes; strict JSON cannot encode it | `unsupported_result_value` |
| An infinite number | Strict JSON cannot encode it | `unsupported_result_value` |
| Six individually small text rows | Large aggregate result | `result_too_large` |
| Eight rows containing control characters | JSON escaping expands the result | `result_too_large` |

These are helper results and standard JSON checks. They do not demonstrate
how LangChain or Mantle serializes binary data, a framework crash, a provider
request size, token count or cost.

## Choose the limits separately

The teaching defaults in `shared/database.py` are:

- At most 100 rows. Too many rows return an error, never an apparently complete
  truncated answer.
- SQLite's `SQLITE_LIMIT_LENGTH` is 16 KiB. It limits strings, binary values
  and records SQLite builds internally, including stored rows and sorting records.
  A plain multi-column result can exceed this limit in total; the complete JSON
  check separately bounds the whole returned response.
- Successful helper results must fit 64 KiB of compact, ASCII-escaped JSON,
  with nonfinite numbers disabled. This includes column names and result
  metadata. It also applies to schema results and the checker's echoed query.

The value limit acts inside SQLite before the Python result is built. The
aggregate limit checks the returned structure: small cells can still add up.
Escaping matters too. A control character that occupied one byte in a cell
takes six ASCII bytes as `\u0001` in this JSON representation.

Binary values are refused rather than silently converted. If your task needs
them, choose an explicit representation and recheck its expansion against the
budget. For long text, select shorter fields or an aggregate useful for the
question. Adding `LIMIT 1` does not make one oversized cell smaller.

These defaults are example policy choices. They are not complete process-memory
or wall-clock limits. JSON formatting, framework envelopes and model
tokenization can change the final request size. The helper retains its
read-only authorizer and opcode progress check; neither replaces customer
authorization or a production service's resource controls.

## Try a smaller query

From the same project directory, run:

```sh
python3 -B exercises/recover_result.py
```

The command uses a fresh temporary database and prints four fixed queries and
results. It does not ask a model to repair a query or use your database.

First, it tries to take a short preview after generating the oversized value:

```sql
SELECT substr(hex(zeroblob(65536)), 1, 80) AS preview
```

That still returns `sqlite_value_too_large`: SQLite must evaluate the large
inner value before the outer substring can trim it. Generating only the small
value succeeds:

```sql
SELECT hex(zeroblob(40)) AS preview
```

This produces the same preview for this all-zero test value. It is not a
replacement for the complete original value, or a general rule about taking
substrings of stored columns. Keep the intended question in view when choosing
what to return.

The other queries ask for counts and total character lengths instead of all
the text. They return `[6, 72000]` and `[8, 12000]` respectively, with named
columns. These summaries answer different questions from returning every value.
Use an aggregate only when it gives the information the user needs; do not
present a summary as the full result.

The supplied queries demonstrate possible changes. The helper's `next_step`
is guidance, not an automatic repair, and a passing helper result does not show
that an agent chose a suitable query or explained the answer correctly.

## Check the contract

```sh
python3 -B -m unittest discover -s tests -p test_result_contract.py -v
```

Expect ten tests followed by `OK`, with no skips. The recovery command has its
own CLI regression:

```sh
python3 -B -m unittest discover -s tests -p test_recovery_exercise.py -v
```

Expect one test followed by `OK`, with no skips. Stop on an error, failure or
skip, and check your selected interpreter and source revision before changing
an expected result.

The controls cover value refusal, combined rows, escaping, finite numbers,
small Unicode and null values, exact budget edges, schema output and the SQL
checker's echo. Each verifies that its local database remains unchanged. Run
the existing `make test` too: a result-budget change must preserve the
read-only and query-work controls.

The helper checks cover the returned data structure. Native binding checks
cover its passage through the tool wrapper. Evaluate the final chat answer
with separate conversation checks.
