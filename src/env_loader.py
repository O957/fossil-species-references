"""
Environment variable loader for API keys.
"""

import os
from pathlib import Path
from typing import Optional


def load_env_file(env_file_path: Path) -> dict:
    """
    Load environment variables from a .env file.

    Parameters
    ----------
    env_file_path : Path
        Path to the .env file.

    Returns
    -------
    dict
        Dictionary of environment variables.
    """
    env_vars = {}

    if not env_file_path.exists():
        return env_vars

    try:
        with open(env_file_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    except Exception as e:
        print(f"Error loading .env file {env_file_path}: {e}")

    return env_vars


def get_bhl_api_key() -> Optional[str]:
    """
    Get BHL API key from environment file or environment variables.

    Returns
    -------
    Optional[str]
        BHL API key or None if not found.
    """
    # First check environment variables
    api_key = os.getenv('BHL_API_KEY')
    if api_key:
        return api_key

    # Then check .env file
    env_file = Path(__file__).parent / '.env' / 'api_keys.env'
    env_vars = load_env_file(env_file)
    return env_vars.get('BHL_API_KEY')


def get_all_api_keys() -> dict:
    """
    Get all API keys from environment.

    Returns
    -------
    dict
        Dictionary of all available API keys.
    """
    api_keys = {}

    # Load from .env file
    env_file = Path(__file__).parent / '.env' / 'api_keys.env'
    env_vars = load_env_file(env_file)

    # Add BHL key
    bhl_key = env_vars.get('BHL_API_KEY') or os.getenv('BHL_API_KEY')
    if bhl_key:
        api_keys['BHL'] = bhl_key

    return api_keys


# Test the loader
if __name__ == "__main__":
    print("Testing API key loader...")

    bhl_key = get_bhl_api_key()
    if bhl_key:
        print(f"✅ BHL API key loaded: {bhl_key[:8]}...")
    else:
        print("❌ BHL API key not found")

    all_keys = get_all_api_keys()
    print(f"All API keys: {list(all_keys.keys())}")