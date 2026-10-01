# Fixtures (fictional)

Everything here is invented. Cedar Clinic, Maria Alvarez, Theo Lindqvist and
their medication records do not exist, and nothing here is medical advice.

- `cedar_clinic.json`: two patients and eight medication entries, including
  two inhalers (so "my inhaler" is ambiguous), a controlled medicine, a
  discontinued one, a request whose acknowledgement is lost
  (`request_service: ack_lost`) and a request service that cannot confirm
  anything (`request_service: unavailable`).
- `case-contract.json`: the casebook contract for `healthcare-refill-request`,
  byte-identical to
  [`tutorials/rasa-ai-team-casebook/examples/healthcare-refill-request.json`](../../../../../rasa-ai-team-casebook/examples/healthcare-refill-request.json).
  A test fails if the two differ.

Both files are copied from
[`examples/mantle-voice-healthcare-refill-request-gpt-local/lib/fixtures/`](../../../../../../examples/mantle-voice-healthcare-refill-request-gpt-local/lib/fixtures/).
