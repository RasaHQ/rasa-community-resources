# Limit the results your SQL tool returns

The shared SQL helper already limits row count and query work. A single row
can still hold a large text value, and a SQLite binary value is not a JSON
string. Check those properties before passing results to an agent.

This exercise uses a temporary local database. It does not download Chinook,
start an agent, install an SDK or make a model call. Use Python 3.12, the
version supported by this project's package. The source SHA and actual Python
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
  and SQLite's encoded rows. Several columns can exceed it together.
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

## Check the contract

```sh
python3 -B -m unittest discover -s tests -p test_result_contract.py -v
```

The controls cover value refusal, combined rows, escaping, finite numbers,
small Unicode and null values, exact budget edges, schema output and the SQL
checker's echo. Each verifies that its local database remains unchanged. Run
the existing `make test` too: a result-budget change must preserve the
read-only and query-work controls.

An accepted helper result does not establish that a chat model answered a
question correctly. Keep native binding and conversation checks separate.
