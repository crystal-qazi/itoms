# Local Development Setup

1. Install Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install `requirements.txt`.
4. Copy `.env.example` to `.env` and configure local values.
5. Run smoke tests with `pytest`.
6. Run locally with `flask --app itoms run`.

Do not use Flask's development server for production deployment. A production WSGI server and deployment-specific configuration will be documented before release.
