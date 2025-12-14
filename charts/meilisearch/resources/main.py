#!/usr/bin/env python3
"""
Meilisearch API Key Provisioner
Generates and validates Meilisearch API keys using the Python client library.
"""

import base64
import os
import sys
import time

import meilisearch
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


def wait_for_meilisearch(client: meilisearch.Client, max_retries: int = 30) -> bool:
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


def validate_api_key(client: meilisearch.Client, api_key: str) -> bool:
    """Validate an API key by testing it against Meilisearch."""
    try:
        test_client = meilisearch.Client(client.config.url, api_key)
        health = test_client.health()
        return health.get("status") == "available"
    except Exception:
        console.print("[yellow]API Key validation failed[/yellow]")
        return False


def create_api_key(
    client: meilisearch.Client,
    description: str,
    indexes: list[str],
    actions: list[str],
) -> str | None:
    """Create a new API key in Meilisearch."""
    try:
        with console.status("[bold cyan]Creating API key..."):
            response = client.create_key(
                options={
                    "name": description,
                    "description": description,
                    "actions": actions,
                    "indexes": indexes,
                    "expiresAt": None,
                }
            )

        key = response.key
        if key:
            console.print(f"[green]✓ API key created: {key[:20]}...[/green]")
            return key
        else:
            console.print("[red]✗ No key returned from Meilisearch[/red]")
            return None
    except Exception as e:
        console.print(f"[red]✗ Failed to create API key: {e}[/red]")
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
    secret_name = get_env("SECRET_NAME", "meilisearch-wikijs-data")
    key_description = get_env("API_KEY_DESCRIPTION", "Wiki.js API Key")
    key_indexes = get_env("API_KEY_INDEXES", "wikijs").split(",")
    key_actions = get_env("API_KEY_ACTIONS", "*").split(",")

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

    # Initialize client
    client = meilisearch.Client(meili_host, meili_master_key)

    # Wait for Meilisearch
    if not wait_for_meilisearch(client):
        console.print("[red]Error: Meilisearch is not responding[/red]")
        sys.exit(1)

    # Check for existing key
    if api_key_value:
        console.print("[cyan]Validating existing API key...[/cyan]")
        if validate_api_key(client, api_key_value):
            console.print("[green]✓ Existing API key is valid[/green]")
            console.print("[bold green]✓ Provisioning complete![/bold green]")
            return

        console.print("[yellow]Existing API key is invalid. Regenerating...[/yellow]")

    # Generate new key
    console.print("[cyan]No valid API key found. Creating new one...[/cyan]")
    new_key = create_api_key(client, key_description, key_indexes, key_actions)

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
