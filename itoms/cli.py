"""Register platform CLI commands."""
from __future__ import annotations

import click
from flask import Flask


def register_cli(app: Flask) -> None:
    """Register migration management command."""
    @app.cli.command("bootstrap-admin")
    def bootstrap_admin() -> None:
        """Interactively create the one-time first department-scoped administrator."""
        from itoms.services.bootstrap import BootstrapError, bootstrap_first_administrator
        click.echo("Run only on a trusted host after applying all migrations.")
        click.echo("This is a one-time operation. Password input is hidden.")
        try:
            employee_id = bootstrap_first_administrator(
                employee_code=click.prompt("Employee code"),
                full_name=click.prompt("Full name"),
                username=click.prompt("Login username"),
                email=click.prompt("Email (optional)", default="", show_default=False),
                department_id=click.prompt("Existing active department ID", type=int),
                password=click.prompt("Initial password", hide_input=True, confirmation_prompt=True),
            )
        except (BootstrapError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Initial administrator created (employee ID: {employee_id}).")
        click.echo("Change the password at first login and enroll TOTP immediately.")

    @app.cli.command("db-migrate")
    def db_migrate() -> None:
        """Apply pending SQL migrations."""
        from itoms.db.migrations.runner import apply_migrations
        applied = apply_migrations()
        if applied:
            click.echo("Applied: " + ", ".join(applied))
        else:
            click.echo("Database is up to date.")
