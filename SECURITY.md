# Security

Do not report security issues in public GitHub issues, pull requests, or Discussions.

## Reporting a vulnerability

Follow the disclosure process at [rasa.com/security-at-rasa/](https://rasa.com/security-at-rasa/).

That channel covers Rasa products and related material, including teaching code in this repository when a report involves secrets handling, unsafe defaults, or other security-sensitive behaviour.

## What belongs here vs elsewhere

| Situation | Where to go |
|---|---|
| Suspected vulnerability in Rasa Pro or related products | [rasa.com/security-at-rasa/](https://rasa.com/security-at-rasa/) |
| Teaching material here no longer runs (non-security) | Open a normal issue in this repository |
| Questions about using the examples | [Discussions](../../discussions/) or the community Discord |

Never commit API keys, licence keys, or production credentials. Resources use `.env` / `.env.example` only.
