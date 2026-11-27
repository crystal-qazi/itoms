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


    @app.cli.command("notifications-process-outbox")
    @click.option("--batch-size", default=25, type=click.IntRange(1, 100))
    def notifications_process_outbox(batch_size: int) -> None:
        """Complete due in-app outbox rows; EMAIL remains queued until an SMTP worker is configured."""
        from itoms.services.notifications import process_in_app_outbox_batch
        processed = process_in_app_outbox_batch(batch_size=batch_size)
        click.echo(f"Completed {processed} in-app outbox item(s).")

    @app.cli.command("notifications-recover-outbox")
    @click.option("--stale-after", default=300, type=click.IntRange(60, 86400))
    def notifications_recover_outbox(stale_after: int) -> None:
        """Recover abandoned notification worker claims."""
        from itoms.services.notifications import recover_stale_outbox
        result = recover_stale_outbox(stale_after_seconds=stale_after)
        click.echo(
            f"Recovered {result['recovered']} item(s); "
            f"dead-lettered {result['dead_lettered']} item(s)."
        )

    @app.cli.command("notifications-replay-outbox")
    @click.argument("outbox_id", type=click.IntRange(1))
    @click.option("--actor-employee-id", required=True, type=click.IntRange(1))
    def notifications_replay_outbox(outbox_id: int, actor_employee_id: int) -> None:
        """Replay one dead-lettered item after checking the actor's explicit permission."""
        from itoms.services.notifications import NotificationError, replay_dead_letter
        try:
            replay_dead_letter(actor_employee_id=actor_employee_id, outbox_id=outbox_id)
        except NotificationError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Outbox item {outbox_id} queued for replay.")

    @app.cli.command("db-migrate")
    def db_migrate() -> None:
        """Apply pending SQL migrations."""
        from itoms.db.migrations.runner import apply_migrations
        applied = apply_migrations()
        if applied:
            click.echo("Applied: " + ", ".join(applied))
        else:
            click.echo("Database is up to date.")
