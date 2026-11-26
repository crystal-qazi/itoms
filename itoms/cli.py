"""Register platform CLI commands."""
from __future__ import annotations

import click
from flask import Flask


def register_cli(app: Flask) -> None:
    """Register migration management command."""
    @app.cli.command("db-migrate")
    def db_migrate() -> None:
        """Apply pending SQL migrations."""
        from itoms.db.migrations.runner import apply_migrations
        applied = apply_migrations()
        if applied:
            click.echo("Applied: " + ", ".join(applied))
        else:
            click.echo("Database is up to date.")
