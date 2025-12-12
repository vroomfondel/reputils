![mypy and pytests](https://github.com/vroomfondel/reputils/actions/workflows/mypynpytests.yml/badge.svg)
![Cumulative Clones](https://img.shields.io/endpoint?logo=github&url=https://gist.githubusercontent.com/vroomfondel/22c802be25a8241e81e98a28d00c6036/raw/reputils_clone_count.json)

![Gemini_Generated_Image_reputils_695z2w695z2w695z_250x250.png](Gemini_Generated_Image_reputils_695z2w695z2w695z_250x250.png)

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

Example: compose and send an email using `MRSendmail`.

```python
from reputils.MailReport import EmailAddress, SMTPServerInfo, MRSendmail

server = SMTPServerInfo(
    smtp_server="smtp.example.com",
    smtp_port=587,
    smtp_user="user@example.com",
    smtp_pass="app-password",
    useStartTLS=True,
)

mailer = MRSendmail(
    serverinfo=server,
    returnpath=EmailAddress(email="bounce@example.com", name="Mailer"),
    senderfrom=EmailAddress(email="noreply@example.com", name="No Reply"),
    subject="Hello from reputils",
)

mailer.addTo(EmailAddress.fromSTR("Alice <alice@example.com>"))

message_id = mailer.send(
    txt="Plain text body",
    html="<p>HTML body</p>",
)

print("Sent with Message-ID:", message_id)
```

Note: See `reputils/MailReport.py` for more details (Cc/Bcc, attachments, additional headers).

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
- `make pypipush` – upload to PyPI via `twine`

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

Upload to PyPI (requires credentials configured for `twine`):

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