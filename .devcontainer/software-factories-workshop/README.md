# New York workshop Codespaces configuration

Start with the [workshop README](../../workshops/software-factories-masterclass/README.md).
It contains the opening link, minute-zero secret setup, recovery steps, and the
single attendee path. No advance setup or local installation is required.

The image contains uv 0.10.8 and the Python feature supplies Python 3.12.
`install.sh` prepares the two committed dependency locks without reading keys;
`setup.sh` checks the participant's repository-scoped secrets after creation.
A running Codespace needs stop/start after a secret changes, followed by an
explicit setup rerun. The model key is checked for presence, not by a paid call.
