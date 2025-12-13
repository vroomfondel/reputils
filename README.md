![mypy and pytests](https://github.com/vroomfondel/reputils/actions/workflows/mypynpytests.yml/badge.svg)
![Cumulative Clones](https://img.shields.io/endpoint?logo=github&url=https://gist.githubusercontent.com/vroomfondel/98e7e1bf08bf1bdefdcc68e96985710d/raw/reputils_clone_count.json)

[![https://github.com/vroomfondel/reputils/raw/main/Gemini_Generated_Image_reputils_695z2w695z2w695z_250x250.png](https://github.com/vroomfondel/reputils/raw/main/Gemini_Generated_Image_reputils_695z2w695z2w695z_250x250.png)](https://github.com/vroomfondel/reputils)

# reputils

Small Python utilities packaged as a library. Currently includes helpers for assembling and sending emails (headers, MIME parts, attachments) with sane defaults, plus a small script used in CI to update a GitHub clones badge via a Gist.

- Source: https://github.com/vroomfondel/reputils
- PyPI: https://pypi.org/project/reputils/

## Overview

This package exposes functionality under the `reputils` module. The main user‑facing component at present is `reputils.MailReport` providing:

- `EmailAddress` dataclass for parsing/formatting email addresses
- `SMTPServerInfo` configuration for SMTP host/port/TLS/etc.
- `MRSendmail` to compose and send text/HTML emails with optional attachments and headers

There is also a maintenance script `scripts/update_badge.py` that is run in GitHub Actions to update a Shields.io JSON endpoint with cumulative repository clone statistics.

## Stack

- Language: Python (requires Python >= 3.12; CI uses Python 3.14)
- Packaging/build: Hatchling (`pyproject.toml`)
- Testing: pytest
- Lint/format: black, isort, mypy
- CI: GitHub Actions (tests/mypy workflow badge shown above) and a scheduled workflow to update a clones badge

## Requirements

Runtime dependencies (see `pyproject.toml` / `requirements.txt`):

- `loguru>=0.7.3`
- `pytz>=2025.2` (packaged as `pytz==2025.2` in `requirements.txt`)
- `python-dateutil==2.9.*`

Development dependencies (see `requirements-dev.txt`):

- `pytest`, `mypy`, `black`, `isort`, `pre-commit`, and typing stubs for dateutil and pytz

Python version: `>=3.12`. The repo’s Makefile and CI use Python 3.14 locally/in CI.

## Installation

Install from PyPI:

```
pip install reputils
```

From source (recommended for development):

```
git clone https://github.com/vroomfondel/reputils
cd reputils
make install
```

The `make install` target creates/uses a local `.venv` and installs dev requirements.

## Usage

### Basic send (text and/or HTML)

`MRSendmail.send()` now returns a tuple `(raw_message: str, result: SendResult)`. The raw string contains the fully rendered RFC 5322 message (including the generated `Message-ID` header). Use the `SendResult` helper to check whether delivery succeeded for all recipients or to inspect per‑recipient failures.

```python
from email import message_from_string
from reputils.MailReport import EmailAddress, SMTPServerInfo, MRSendmail

server = SMTPServerInfo(
    smtp_server="smtp.example.com",
    smtp_port=587,
    smtp_user="user@example.com",
    smtp_pass="app-password",
    use_start_tls=True,
)

mailer = MRSendmail(
    serverinfo=server,
    returnpath=EmailAddress(email="bounce@example.com", name="Mailer"),
    senderfrom=EmailAddress(email="noreply@example.com", name="No Reply"),
    subject="Hello from reputils",
)

mailer.add_to(EmailAddress.from_str("Alice <alice@example.com>"))

raw, res = mailer.send(
    txt="Plain text body",
    html="<p>HTML body</p>",
)

print("All recipients succeeded:", res.all_succeeded())
# Extract the Message-ID from the rendered message if you need it:
msg = message_from_string(raw)
print("Message-ID:", msg["Message-ID"])  # e.g. <20250101...@example.com>
```

### Cc/Bcc, attachments, and additional headers

```python
from pathlib import Path
from reputils.MailReport import EmailAddress, SMTPServerInfo, MRSendmail

# Create or reuse a mailer instance (example shown inline for completeness)
server = SMTPServerInfo(smtp_server="smtp.example.com", smtp_port=587, use_start_tls=True)
mailer = MRSendmail(
    serverinfo=server,
    returnpath=EmailAddress(email="bounce@example.com", name="Mailer"),
    senderfrom=EmailAddress(email="noreply@example.com", name="No Reply"),
    subject="Monthly report",
)

mailer.add_to(EmailAddress.from_str("Alice <alice@example.com>"))
mailer.add_cc(EmailAddress.from_str("Bob <bob@example.com>"))
mailer.add_bcc(EmailAddress.from_str("carol@example.com"))

raw, res = mailer.send(
    txt="Report attached.",
    files=[Path("/tmp/report.txt"), Path("/tmp/plot.png")],
    additional_headers={
        "X-Trace-ID": "12345",
        "List-Id": "example.list.example.com",
    },
)

if not res.all_succeeded():
    # Inspect per‑recipient SMTP errors (email, code, message)
    for email, code, message in res.get_all_errors():
        print(f"Failed: {email} -> {code} {message}")
```

### Unicode (Umlauts/Accents) work out of the box

`MailReport` composes messages using UTF‑8 and quoted‑printable encodings for both headers and bodies. That means subjects, display names, and message content with Umlauts and other non‑ASCII characters are sent correctly (e.g. Ä Ö Ü ä ö ü ß, accents like é, ñ, ą, …).

Example:

```python
from reputils.MailReport import EmailAddress, SMTPServerInfo, MRSendmail

server = SMTPServerInfo(smtp_server="smtp.example.com", smtp_port=587, use_start_tls=True)
mailer = MRSendmail(
    serverinfo=server,
    returnpath=EmailAddress(email="bounce@example.com", name="Mailer"),
    senderfrom=EmailAddress(email="noreply@example.com", name="München Prüfstelle"),
    subject="Status für Prüfstände – Größe ist größer",
)

mailer.add_to(EmailAddress(email="alice@example.com", name="Jörg Hübner"))

txt_body = "Hallo Jörg, die Größe ist größer als erwartet. Grüße aus München!"
html_body = "<p>Hallo Jörg, die Größe ist <b>größer</b> als erwartet. Grüße aus München!</p>"

raw, res = mailer.send(txt=txt_body, html=html_body)
assert res.all_succeeded()
```

No additional configuration is required; Python’s `email` package handles RFC 2047/2045 encoding under the hood, and `reputils.MailReport` sets sane UTF‑8 defaults.

### SMTP and application‑level debug logging per send

```python
from reputils.MailReport import SMTPServerInfo, MRSendmail, EmailAddress

server = SMTPServerInfo(smtp_server="smtp.example.com", smtp_port=587)
mailer = MRSendmail(serverinfo=server, returnpath=EmailAddress(email="bounce@example.com"))

# Low‑level smtplib debugging for this call
raw, res = mailer.send(txt="Hello", wants_smtp_level_debug=True)

# More verbose application‑level logging from MRSendmail for this call
raw, res = mailer.send(txt="Hello", wantsdebuglogging=True)
```

### Logging configuration with Loguru (optional)

`MailReport` uses `loguru` for logging. To enable a reasonable default console configuration with a built‑in “skiplog” filter, call:

```python
from reputils.MailReport import configure_loguru_default_with_skiplog_filter

configure_loguru_default_with_skiplog_filter()
```

See also `scripts/loguru_skiplog_config_example.py` for a minimal example.

## Scripts and Automation

- `scripts/update_badge.py`: Updates a Gist with clone history and a Shields.io JSON for a “Cumulative Clones” badge. This is executed by `.github/workflows/update-clone-badge.yml` on a schedule or manual dispatch.

Environment variables required by the script/CI workflow:

- `GIST_TOKEN`: GitHub token with permission to update the target Gist
- `GIST_ID`: ID of the Gist storing history and badge JSON
- `REPO_TOKEN`: GitHub token to read repository traffic stats
- `GITHUB_REPOSITORY`: full repo slug, e.g. `owner/repository`

Local ad‑hoc run:

```
GIST_TOKEN=... GIST_ID=... REPO_TOKEN=... GITHUB_REPOSITORY=vroomfondel/reputils \
python scripts/update_badge.py
```

## Makefile Targets

Convenience tasks are provided via `Makefile`:

- `make install` – create `.venv` and install dev requirements
- `make tests` – run pytest
- `make tcheck` – run mypy type checks
- `make lint` – run black
- `make isort` – fix import order
- `make prepare` – run tests and pre‑commit checks
- `make pypibuild` – build distribution with `hatchling`/`build`
- `make pypipush` – upload to PyPI via `hatch`

Note: The Makefile activates `.venv` automatically for these targets when not running in GitHub Actions.

## Running Tests

```
make tests
```

Pytest is configured via `pytest.ini`. Current tests are minimal (see `tests/test_base.py`).

## Project Structure

```
reputils/
├─ reputils/
│  ├─ __init__.py
│  └─ MailReport.py              # Email utilities
├─ scripts/
│  └─ update_badge.py            # CI helper for clone badge
├─ tests/
│  ├─ __init__.py
│  ├─ conftest.py
│  └─ test_base.py
├─ pyproject.toml                 # Hatchling project config
├─ requirements.txt               # Runtime deps
├─ requirements-dev.txt           # Dev/test tools
├─ requirements-build.txt         # Build/upload tools
├─ Makefile                       # Dev tasks and packaging
├─ pytest.ini
├─ LICENSE
└─ README.md
```

## Environment Variables

- For CI badge update: `GIST_TOKEN`, `GIST_ID`, `REPO_TOKEN`, `GITHUB_REPOSITORY` (see Scripts section).
- TODO: Document any runtime configuration for `reputils` if/when added. At present, logging for the `reputils` logger is disabled by default in code.

## Build and Publish

Build wheels/sdist:

```
make pypibuild
```

Upload to PyPI (requires credentials configured for `hatch` resp. `${HOME}/.pypirc` properly filled):

```
make pypipush
```

Artifacts are produced in the `dist/` directory. The version is managed in `pyproject.toml`.

## Entry Points / CLI

No console scripts/entry points are currently defined in `pyproject.toml`.

## License

MIT License. See the `LICENSE` file.

## Changelog / Roadmap

- TODO: Add a CHANGELOG or release notes.
- TODO: Document additional modules if added in the future.

## ⚠️ Disclaimer

This is a development/experimental project. For production use, review security settings, customize configurations, and test thoroughly in your environment. Provided "as is" without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection with the software or the use or other dealings in the software. Use at your own risk.