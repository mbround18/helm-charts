#!/usr/bin/env python3
"""
Meilisearch API Key Provisioner
Generates and validates Meilisearch API keys using the Python client library.
"""

import argparse
import base64
import logging
import os
import sys
import time
from typing import Optional
from contextlib import contextmanager
from typing import Iterator, Any

from meilisearch import Client  # type: ignore[attr-defined]

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@contextmanager
def meili_client_ctx(host: str, key: Optional[str]) -> Iterator[Client]:
    """Context manager for Meilisearch Client."""
    client = Client(host, key)
    try:
        yield client
    finally:
        # client has no close method; leave for GC
        pass


@contextmanager
def kube_client_ctx(kube_config: Optional[str] = None) -> Iterator[Any]:
    """Context manager for Kubernetes CoreV1Api client."""
    from kubernetes import client as k8s_client  # type: ignore
    from kubernetes import config as k8s_config  # type: ignore

    if kube_config:
        k8s_config.load_kube_config(config_file=kube_config)
    else:
        try:
            k8s_config.load_incluster_config()
        except Exception:
            # Fall back to kube_config if in-cluster not available
            if kube_config:
                k8s_config.load_kube_config(config_file=kube_config)
    v1 = k8s_client.CoreV1Api()
    try:
        yield v1
    finally:
        pass


def get_env(var: str, default: str | None = None) -> str:
    """Get environment variable with optional default."""
    value = os.getenv(var, default)
    if not value and default is None:
        logger.error("Error: %s not set", var)
        sys.exit(1)
    return value if value else default  # type: ignore[return-value]


def wait_for_meilisearch(client: Client, max_retries: int = 30) -> bool:
    """Wait for Meilisearch to be ready."""
    for attempt in range(max_retries):
        try:
            health = client.health()
            if health.get("status") == "available":
                logger.info("Meilisearch is ready")
                return True
        except Exception:
            if attempt == max_retries - 1:
                logger.error("Failed after %d attempts", max_retries)
                return False
            time.sleep(2)
    return False


def validate_master_key(client: Client) -> bool:
    """Validate the master key by testing it against Meilisearch."""
    try:
        # Health endpoint may be accessible without auth; require an admin
        # operation (listing keys) to verify the provided master key.
        health = client.health()
        if health.get("status") != "available":
            logger.error("Meilisearch health check failed")
            return False

        try:
            client.get_keys()
            logger.info("Master key is valid and has key-management permissions")
            return True
        except Exception as key_err:
            logger.error(
                "Master key does not have key-management permissions: %s", key_err
            )
            return False
    except Exception as e:
        logger.error("Master key validation failed: %s", e)
        return False


def validate_api_key(url: str, api_key: str) -> bool:
    """Validate an API key by testing it against Meilisearch."""
    try:
        test_client = Client(url, api_key)
        health = test_client.health()
        return health.get("status") == "available"
    except Exception:
        return False


def find_matching_key(
    client: Client,
    host_url: str,
    description: str,
    indexes: list[str],
    actions: list[str],
) -> str | None:
    """Search existing API keys for one that matches the requested criteria.

    Matching rules:
    - If a key's description/name matches `description`, prefer it.
    - Otherwise accept a key where the key's `indexes` and `actions` are
      supersets of the requested ones (or contain "*").
    Returns the key string if found and valid, otherwise None.
    """
    try:
        raw = client.get_keys()
    except Exception as e:
        logger.warning("Warning: failed to list keys: %s", e)
        return None

    # Support different return shapes (dict with 'results' or list)
    keys_list = (
        raw.get("results") if isinstance(raw, dict) and raw.get("results") else raw
    )

    # Normalize requested sets
    req_indexes = set(indexes) if indexes and indexes != ["*"] else None
    req_actions = set(actions) if actions and actions != ["*"] else None

    # Helper to extract fields robustly
    def _get(k, *names):
        for n in names:
            if isinstance(k, dict) and n in k:
                return k[n]
            val = getattr(k, n, None)
            if val is not None:
                return val
        return None

    # First pass: exact description match
    for k in keys_list or []:
        name = _get(k, "name", "description") or ""
        key_val = _get(k, "key", "value", "uid")
        if not key_val:
            continue
        if name and name == description:
            if validate_api_key(host_url, key_val):
                logger.info("Found existing key by description: %s", name)
                return key_val

    # Second pass: find by actions/indexes superset
    for k in keys_list or []:
        k_indexes = _get(k, "indexes") or []
        k_actions = _get(k, "actions") or []
        key_val = _get(k, "key", "value", "uid")
        if not key_val:
            continue

        # Normalize lists
        k_indexes_set = set(k_indexes) if k_indexes and k_indexes != ["*"] else None
        k_actions_set = set(k_actions) if k_actions and k_actions != ["*"] else None

        ok_indexes = True
        ok_actions = True

        if req_indexes is not None:
            if k_indexes_set is None:
                ok_indexes = True
            else:
                ok_indexes = req_indexes.issubset(k_indexes_set)

        if req_actions is not None:
            if k_actions_set is None:
                ok_actions = True
            else:
                ok_actions = req_actions.issubset(k_actions_set)

        if ok_indexes and ok_actions:
            if validate_api_key(host_url, key_val):
                logger.info(
                    "Found existing key matching actions/indexes: %s...",
                    key_val[:20],
                )
                return key_val

    return None


def ensure_indexes(client: Client, indexes: list[str]) -> None:
    """Create any missing indexes in Meilisearch using the master client.

    Skips when indexes is ['*'] (meaning all indexes).
    """
    if not indexes or indexes == ["*"]:
        logger.info("Index creation skipped (wildcard '*')")
        return

    for idx in indexes:
        idx = idx.strip()
        if not idx:
            continue
        try:
            # Try to fetch the index; if it exists this will succeed
            try:
                client.get_index(idx)
                logger.info("Index exists: %s", idx)
            except Exception as ms:
                logger.warning("Index %s not found: %s", idx, ms)
                logger.warning("Index %s missing — creating...", idx)
                try:
                    # Try common signatures for create_index
                    try:
                        client.create_index(uid=idx)
                    except TypeError:
                        client.create_index(idx)
                    logger.info("Created index: %s", idx)
                except Exception as ce:
                    logger.error("Failed to create index %s: %s", idx, ce)
        except Exception as e:
            logger.warning("Warning checking/creating index %s: %s", idx, e)


def create_api_key(
    client: Client,
    description: str,
    indexes: list[str],
    actions: list[str],
) -> str | None:
    """Create a new API key in Meilisearch using master key client."""
    # Clean and validate input
    valid_indexes = [idx.strip() for idx in indexes if idx.strip()]
    valid_actions = [act.strip() for act in actions if act.strip()]

    logger.info("Using indexes: %s", valid_indexes)
    logger.info("Using actions: %s", valid_actions)

    # Use a more specific name to make keys easier to match and avoid
    # multiple ambiguous "Provisioned API Key" entries.
    specific_name = f"{description} ({os.getenv('NAMESPACE', 'default')}/{os.getenv('SECRET_NAME', 'meilisearch-api-key')})"
    try:
        response = client.create_key(
            options={
                "name": specific_name,
                "description": description,
                "actions": valid_actions,
                "indexes": valid_indexes,
                "expiresAt": None,
            }
        )

        # Response is a Key object with a .key attribute (str)
        key = response.key  # type: ignore[attr-defined]
        if key and isinstance(key, str) and len(key) > 0:
            logger.info("API key created: %s...", key[:20])
            return key
        else:
            logger.error("No key returned from Meilisearch")
            return None
    except Exception:
        logger.exception("Failed to create API key")
        return None


def patch_secret(
    namespace: str,
    secret_name: str,
    api_key: str,
    kube_config: Optional[str] = None,
    kube_v1: Optional[Any] = None,
    dry_run: bool = False,
) -> bool:
    """Patch the Kubernetes secret with the API key using the Python client."""
    try:
        # Use provided kube_v1 client when available to reuse connections
        if kube_v1 is not None:
            v1 = kube_v1
        else:
            from kubernetes import client as k8s_client  # type: ignore
            from kubernetes import config as k8s_config  # type: ignore

            if kube_config:
                k8s_config.load_kube_config(config_file=kube_config)
            else:
                k8s_config.load_incluster_config()
            v1 = k8s_client.CoreV1Api()

        # Get existing secret
        secret = v1.read_namespaced_secret(secret_name, namespace)

        # Update the api-key field
        if getattr(secret, "data", None) is None:  # type: ignore[union-attr]
            setattr(secret, "data", {})

        # Encode the key as base64
        secret.data["api-key"] = base64.b64encode(api_key.encode()).decode()  # type: ignore[index]

        # Patch the secret
        if dry_run:
            logger.warning(
                "Dry-run: would patch secret %s in %s", secret_name, namespace
            )
        else:
            v1.patch_namespaced_secret(secret_name, namespace, secret)

        logger.info("Secret %s updated", secret_name)
        return True
    except Exception as e:
        logger.error("Error updating secret: %s", e)
        return False


def read_secret_api_key(
    namespace: str,
    secret_name: str,
    kube_config: Optional[str] = None,
    kube_v1: Optional[Any] = None,
) -> Optional[str]:
    """Read `api-key` from a Kubernetes secret if present (returns decoded string).

    Returns None if the secret or key is missing or on error.
    """
    try:
        if kube_v1 is not None:
            v1 = kube_v1
        else:
            from kubernetes import client as k8s_client  # type: ignore
            from kubernetes import config as k8s_config  # type: ignore

            if kube_config:
                k8s_config.load_kube_config(config_file=kube_config)
            else:
                k8s_config.load_incluster_config()
            v1 = k8s_client.CoreV1Api()

        secret = v1.read_namespaced_secret(secret_name, namespace)
        data = getattr(secret, "data", None)
        if not data:
            return None
        api_b64 = data.get("api-key") or data.get("api_key")
        if not api_b64:
            return None
        try:
            return base64.b64decode(api_b64).decode()
        except Exception:
            return None
    except Exception as e:
        logger.debug("Could not read secret %s/%s: %s", namespace, secret_name, e)
        return None


def main():
    """Main provisioning flow."""
    logger.info("Meilisearch API Key Provisioner")

    # CLI / Environment variables
    parser = argparse.ArgumentParser(description="Meilisearch API Key Provisioner")
    parser.add_argument(
        "--meili-host", default=os.getenv("MEILI_HOST", "http://meilisearch:7700")
    )
    parser.add_argument("--meili-master-key", default=os.getenv("MEILI_MASTER_KEY"))
    parser.add_argument("--meili-api-key", default=os.getenv("MEILI_API_KEY", ""))
    parser.add_argument("--namespace", default=os.getenv("NAMESPACE", "default"))
    parser.add_argument(
        "--secret-name", default=os.getenv("SECRET_NAME", "meilisearch-api-key")
    )
    parser.add_argument(
        "--api-key-description",
        default=os.getenv("API_KEY_DESCRIPTION", "Provisioned API Key"),
    )
    parser.add_argument("--api-key-indexes", default=os.getenv("API_KEY_INDEXES", "*"))
    parser.add_argument("--api-key-actions", default=os.getenv("API_KEY_ACTIONS", "*"))
    parser.add_argument("--kube-config", default=os.getenv("KUBECONFIG", None))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not patch Kubernetes secret; just print actions",
    )

    args = parser.parse_args()

    meili_host = args.meili_host
    meili_master_key = args.meili_master_key
    api_key_value = args.meili_api_key.strip()
    namespace = args.namespace
    secret_name = args.secret_name
    key_description = args.api_key_description
    key_indexes_input = args.api_key_indexes.split(",")
    key_actions_input = args.api_key_actions.split(",")
    kube_config = args.kube_config
    dry_run = args.dry_run

    # Use ["*"] if the input contains "*" to allow all
    key_indexes = ["*"] if "*" in key_indexes_input else key_indexes_input
    key_actions = ["*"] if "*" in key_actions_input else key_actions_input

    # Display configuration
    logger.info(
        "Configuration: host=%s namespace=%s secret=%s description=%s indexes=%s actions=%s",
        meili_host,
        namespace,
        secret_name,
        key_description,
        ",".join(key_indexes),
        ",".join(key_actions),
    )

    # Use context managers to reuse clients
    with meili_client_ctx(meili_host, meili_master_key) as master_client:
        with kube_client_ctx(kube_config) as kube_v1:
            # Wait for Meilisearch
            if not wait_for_meilisearch(master_client):
                logger.error("Error: Meilisearch is not responding")
                sys.exit(1)

            # Validate master key
            logger.info("Validating master key...")
            if not validate_master_key(master_client):
                logger.error("Error: Master key is invalid")
                sys.exit(1)

            # Ensure requested indexes exist (creates missing ones)
            ensure_indexes(master_client, key_indexes)

            # Check for provided API key first
            if api_key_value:
                logger.info("Validating provided API key...")
                if validate_api_key(meili_host, api_key_value):
                    logger.info("Provided API key is valid")
                    logger.info("Provisioning complete!")
                    return

                logger.warning(
                    "Provided API key is invalid. Searching for reusable key..."
                )

            # Try reading existing Kubernetes secret (if available) and reuse it
            existing_secret_key = read_secret_api_key(
                namespace, secret_name, kube_config, kube_v1=kube_v1
            )
            if existing_secret_key:
                logger.info(
                    "Found existing Kubernetes secret %s/%s, validating...",
                    namespace,
                    secret_name,
                )
                if validate_api_key(meili_host, existing_secret_key):
                    logger.info(
                        "Kubernetes secret contains a valid API key; provisioning complete"
                    )
                    return
                else:
                    logger.warning(
                        "Kubernetes secret %s/%s contains invalid key; continuing",
                        namespace,
                        secret_name,
                    )

            # Try to find and reuse an existing key that matches our criteria
            existing = find_matching_key(
                master_client, meili_host, key_description, key_indexes, key_actions
            )
            if existing:
                logger.info("Reusing existing matching API key")
                if patch_secret(
                    namespace,
                    secret_name,
                    existing,
                    kube_config=kube_config,
                    kube_v1=kube_v1,
                    dry_run=dry_run,
                ):
                    logger.info("Provisioning complete!")
                    return
                else:
                    logger.warning(
                        "Warning: failed to patch secret with existing key; will attempt to create a new key"
                    )

            # Generate new key using master client
            logger.info("No valid API key found. Creating new one...")
            new_key = create_api_key(
                master_client, key_description, key_indexes, key_actions
            )

            if not new_key:
                logger.error("Error: Failed to create API key")
                sys.exit(1)

            # Patch secret
            if not patch_secret(
                namespace,
                secret_name,
                new_key,
                kube_config=kube_config,
                kube_v1=kube_v1,
                dry_run=dry_run,
            ):
                logger.error("Error: Failed to update secret")
                sys.exit(1)
            logger.info("Provisioning complete!")


if __name__ == "__main__":
    main()
