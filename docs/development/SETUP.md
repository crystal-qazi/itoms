# Local Development Setup

## Prerequisites

- Python 3.11 or newer
- MySQL 8.4
- Git

## Create an isolated environment

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Linux/macOS:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with a dedicated disposable development database and generated secrets. The Flask CLI loads `.env` through `python-dotenv`; production WSGI processes should receive settings from the operating-system service environment or an approved secret manager.

Generate local keys:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set those values as `ITOMS_SECRET_KEY` and `ITOMS_TOTP_ENCRYPTION_KEY`. Configure MySQL values with the `ITOMS_DB_*` prefix. Set `ITOMS_DOCUMENT_STORAGE_ROOT` to a dedicated directory outside the repository, application root and static directory. Configure Trend Micro ICAP before testing document upload.

## Initialize the database

Create an empty database and a dedicated development account in MySQL 8.4. Apply migrations:

```bash
flask --app itoms db-migrate
```

Create an active department and then bootstrap the first administrator:

```bash
flask --app itoms bootstrap-admin
```

The bootstrap command prompts for the existing department ID and an operator-supplied initial password. It does not create a default account or password. At first login, the administrator must change the password and enroll TOTP.

## Run checks and the development server

```bash
python -m compileall -q itoms
pytest -q
flask --app itoms run
```

MySQL integration tests are run by CI against a disposable MySQL 8.4 database. Never point test fixtures at production data.

The Flask development server is for local development only. See [Production Deployment](PRODUCTION_DEPLOYMENT.md) for the WSGI serving baseline and production safety gates.
