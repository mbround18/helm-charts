#!/usr/bin/env python3
"""
Meilisearch API Key Provisioner
Generates and validates Meilisearch API keys using the Python client library.
"""

import base64
import os
import sys
import time

from meilisearch import Client  # type: ignore[attr-defined]
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def get_env(var: str, default: str | None = None) -> str:
    """Get environment variable with optional default."""
    value = os.getenv(var, default)
    if not value and default is None:
        console.print(f"[red]Error: {var} not set[/red]")
        sys.exit(1)
    return value if value else default  # type: ignore[return-value]


def wait_for_meilisearch(client: Client, max_retries: int = 30) -> bool:
    """Wait for Meilisearch to be ready."""
    with console.status("[bold cyan]Waiting for Meilisearch to be ready..."):
        for attempt in range(max_retries):
            try:
                health = client.health()
                if health.get("status") == "available":
                    console.print("[green]✓ Meilisearch is ready[/green]")
                    return True
            except Exception:
                if attempt == max_retries - 1:
                    console.print(f"[red]✗ Failed after {max_retries} attempts[/red]")
                    return False
                time.sleep(2)
    return False


def validate_master_key(client: Client) -> bool:
    """Validate the master key by testing it against Meilisearch."""
    try:
        health = client.health()
        is_valid = health.get("status") == "available"
        if is_valid:
            console.print("[green]✓ Master key is valid[/green]")
            # Also try to list keys to verify permissions
            try:
                client.get_keys()
                console.print("[green]✓ Master key has permission to manage keys[/green]")
            except Exception as key_err:
                console.print(f"[yellow]⚠ Warning: Master key cannot list keys: {key_err}[/yellow]")
        else:
            console.print("[red]✗ Master key validation failed[/red]")
        return is_valid
    except Exception as e:
        console.print(f"[red]✗ Master key validation failed: {e}[/red]")
        return False


def validate_api_key(url: str, api_key: str) -> bool:
    """Validate an API key by testing it against Meilisearch."""
    try:
        test_client = Client(url, api_key)
        health = test_client.health()
        return health.get("status") == "available"
    except Exception:
        return False


def create_api_key(
    client: Client,
    description: str,
    indexes: list[str],
    actions: list[str],
) -> str | None:
    """Create a new API key in Meilisearch using master key client."""
    try:
        with console.status("[bold cyan]Creating API key..."):
            # Clean and validate input
            valid_indexes = [idx.strip() for idx in indexes if idx.strip()]
            valid_actions = [act.strip() for act in actions if act.strip()]

            console.print(f"[cyan]Using indexes: {valid_indexes}[/cyan]")
            console.print(f"[cyan]Using actions: {valid_actions}[/cyan]")

            response = client.create_key(
                options={
                    "name": description,
                    "description": description,
                    "actions": valid_actions,
                    "indexes": valid_indexes,
                    "expiresAt": None,
                }
            )

        # Response is a Key object with a .key attribute (str)
        key = response.key  # type: ignore[attr-defined]
        if key and isinstance(key, str) and len(key) > 0:
            console.print(f"[green]✓ API key created: {key[:20]}...[/green]")
            return key
        else:
            console.print("[red]✗ No key returned from Meilisearch[/red]")
            return None
    except Exception as e:
        console.print(f"[red]✗ Failed to create API key: {e}[/red]")
        # Print full error details for debugging
        import traceback

        console.print(f"[yellow]Debug trace: {traceback.format_exc()}[/yellow]")
        return None


def patch_secret(namespace: str, secret_name: str, api_key: str) -> bool:
    """Patch the Kubernetes secret with the API key using the Python client."""
    try:
        # Load in-cluster configuration
        k8s_config.load_incluster_config()
        v1 = k8s_client.CoreV1Api()

        with console.status(f"[bold cyan]Updating secret {secret_name}..."):
            # Get existing secret
            secret = v1.read_namespaced_secret(secret_name, namespace)

            # Update the api-key field
            if secret.data is None:  # type: ignore[union-attr]
                secret.data = {}

            # Encode the key as base64
            secret.data["api-key"] = base64.b64encode(api_key.encode()).decode()  # type: ignore[index]

            # Patch the secret
            v1.patch_namespaced_secret(secret_name, namespace, secret)

        console.print(f"[green]✓ Secret {secret_name} updated[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ Error updating secret: {e}[/red]")
        return False


def main():
    """Main provisioning flow."""
    console.print(
        Panel.fit(
            "[bold cyan]Meilisearch API Key Provisioner[/bold cyan]",
            border_style="cyan",
        )
    )

    # Environment variables
    meili_host = get_env("MEILI_HOST", "http://meilisearch:7700")
    meili_master_key = get_env("MEILI_MASTER_KEY")
    api_key_value = os.getenv("MEILI_API_KEY", "").strip()
    namespace = get_env("NAMESPACE", "default")
    secret_name = get_env("SECRET_NAME", "meilisearch-api-key")
    key_description = get_env("API_KEY_DESCRIPTION", "Provisioned API Key")
    key_indexes_input = get_env("API_KEY_INDEXES", "*").split(",")
    key_actions_input = get_env("API_KEY_ACTIONS", "*").split(",")

    # Use ["*"] if the input contains "*" to allow all
    key_indexes = ["*"] if "*" in key_indexes_input else key_indexes_input
    key_actions = ["*"] if "*" in key_actions_input else key_actions_input

    # Initialize master key client (reuse throughout)
    master_client = Client(meili_host, meili_master_key)

    # Display configuration
    config_table = Table(title="Configuration", show_header=False)
    config_table.add_row("Meilisearch Host", meili_host)
    config_table.add_row("Namespace", namespace)
    config_table.add_row("Secret Name", secret_name)
    config_table.add_row("Key Description", key_description)
    config_table.add_row("Indexes", ", ".join(key_indexes))
    config_table.add_row("Actions", ", ".join(key_actions))
    console.print(config_table)
    console.print()

    # Wait for Meilisearch
    if not wait_for_meilisearch(master_client):
        console.print("[red]Error: Meilisearch is not responding[/red]")
        sys.exit(1)

    # Validate master key
    console.print("[cyan]Validating master key...[/cyan]")
    if not validate_master_key(master_client):
        console.print("[red]Error: Master key is invalid[/red]")
        sys.exit(1)

    # Check for existing key
    if api_key_value:
        console.print("[cyan]Validating existing API key...[/cyan]")
        if validate_api_key(meili_host, api_key_value):
            console.print("[green]✓ Existing API key is valid[/green]")
            console.print("[bold green]✓ Provisioning complete![/bold green]")
            return

        console.print("[yellow]Existing API key is invalid. Regenerating...[/yellow]")

    # Generate new key using master client
    console.print("[cyan]No valid API key found. Creating new one...[/cyan]")
    new_key = create_api_key(master_client, key_description, key_indexes, key_actions)

    if not new_key:
        console.print("[red]Error: Failed to create API key[/red]")
        sys.exit(1)

    # Patch secret
    if not patch_secret(namespace, secret_name, new_key):
        console.print("[red]Error: Failed to update secret[/red]")
        sys.exit(1)

    console.print()
    console.print(
        Panel.fit(
            "[bold green]✓ Provisioning complete![/bold green]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
