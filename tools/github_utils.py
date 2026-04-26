import os
import subprocess
import sys


def get_github_token() -> str | None:
    """
    Attempts to retrieve a GitHub token from environment variables or gh CLI.
    Returns the token string if found, otherwise None.
    """
    # 1. Check GITHUB_TOKEN environment variable
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return token

    # 2. Try gh CLI
    try:
        # Check if gh CLI is installed
        subprocess.run(["which", "gh"], check=True, capture_output=True)

        # Get token using gh auth token
        # Using --hostname github.com to ensure we get the token for the main GitHub
        # This might need to be configurable if dealing with GitHub Enterprise
        token_proc = subprocess.run(
            ["gh", "auth", "token", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            check=True,
        )
        token = token_proc.stdout.strip()
        if token:
            return token
    except subprocess.CalledProcessError, FileNotFoundError:
        print(
            "Warning: Neither GITHUB_TOKEN environment variable nor 'gh' CLI token found.",
            file=sys.stderr,
        )
        print(
            "         GHCR authentication might fail or hit rate limits for private repositories.",
            file=sys.stderr,
        )
        pass  # gh CLI not found or not logged in

    return None


if __name__ == "__main__":
    # Example usage
    token = get_github_token()
    if token:
        print(f"GitHub Token found (first 5 chars): {token[:5]}*****")
    else:
        print("No GitHub Token found.")
