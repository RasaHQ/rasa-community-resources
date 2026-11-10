# Explain what you built

Use these prompts at your own pace. Answer before reading the notes. You do not need a facilitator to decide whether to move on.

| Checkpoint | Show | Explain |
|---|---|---|
| Your helper | The four rows: a confirmation, `REBOOT` after yes, a question for "reset", a refusal with an offer of a person | What did you observe at each row, and what did the helper record? Where could the wording differ and the meaning still match? |
| Change your mind | The helper after you ask for a restart and then decline | What did it record, and how do you know? |
| Source-file check | `PASS`, then `FAIL` after you change `REBOOT` to `FACTORY_RESET`, then `PASS` after you restore it | What did the check read? What can it not tell you about a live conversation? Why restore `REBOOT` before you retrain? |
| Your builder | The mode (fixture or live), the build id, the absolute path and the sha256 | Which of these did the builder report, and which did you check yourself? Did an Agents session run? |
| Behind the helper | The helper's reply to the line-status request | Which words showed a build started and saved a file? What does "Nothing was applied" mean? |
| The gate | `ACCEPT` for `good.py` and your file (if it passes), `REJECT` for the three `bad_` files | What did each `bad_` file try to do? Why does the gate not run the file? |
| Your decision | Your written approval or refusal | What evidence did you use? What did you not check? |

## Notes to compare with your answer

- Each row is one observation. A table of four passing rows says how the helper answered, not how it will answer every customer.
- The source-file check reads a file. The conversation checks read replies. They agree only if you check both. Restore `REBOOT` and see `PASS` again before moving on, because the later steps retrain the helper from that file.
- A fixture build copies a public sample and starts no Agents session. It tests file handling, the tool transport, the receipt and the gate. It does not test code generation. A live build uses your key and is billed, and its cost was not measured.
- The path and sha256 are a receipt for one file. The gate separately judges that file's bytes. Neither says the file was applied, because nothing is applied to the helper.
- The gate accepts one small kind of file. A `REJECT` names a test that failed. "Could not judge" is not a `REJECT`.
- Your approval or refusal is a record for manual review. A gate `ACCEPT` is not a deployment.

## Your two-minute handoff

Show one request, one failure, the exact output you accepted or refused, and one limit. Say for each part whether it was observed in your codespace or only described. A useful final question: what evidence would another person need to trust your decision without reading every changed line?
