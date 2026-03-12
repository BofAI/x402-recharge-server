# Contributing

## Setup

Use Python 3.11 or newer.

Recommended local setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you need to run ERC-8004 registration scripts, also install the SDK:

```bash
pip install git+https://github.com/BofAI/8004-sdk.git#subdirectory=python
```

## Change Scope

Keep runtime, deployment, and registration changes separate when possible:

- MCP runtime behavior: `server.py`, `src/`, `config/`
- deployment and smoke tests: `docker-compose.yml`, `scripts/deploy.sh`, `DEPLOYMENT.md`
- ERC-8004 registration flow: `scripts/register_8004.py`, `scripts/update_8004.py`, `scripts/render_registration.py`, `docs/REGISTRATION.md`

## Before Opening a PR

- run the relevant script help commands
- validate JSON examples if you changed registration templates
- update `README.md` and `docs/REGISTRATION.md` when changing operator workflow
- document externally visible changes in `CHANGELOG.md`

Suggested checks:

```bash
python3 -m py_compile server.py scripts/*.py src/*.py
python3 scripts/render_registration.py --help
python3 scripts/upload_to_pinata.py --help
python3 scripts/register_8004.py --help
python3 scripts/update_8004.py --help
```

## Pull Requests

Include:

- what changed
- why it changed
- how you tested it
- any required environment or credential assumptions

Avoid including real private keys, merchant secrets, or live production JWTs in examples, logs, or screenshots.
