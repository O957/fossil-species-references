"""
Configuration loader for the fossil species references application.
"""

import tomllib
from pathlib import Path

# Load configuration
_config_path = Path(__file__).parent / "config.toml"
with open(_config_path, "rb") as f:
    _config = tomllib.load(f)

# API constants
PBDB_BASE_URL = _config["api"]["pbdb_base_url"]
DEFAULT_TIMEOUT = _config["api"]["default_timeout"]
NOT_AVAILABLE = _config["api"]["not_available"]
API_DELAY = _config["api"]["api_delay"]

# External API constants
CROSSREF_BASE_URL = _config["external_apis"]["crossref_base_url"]
BHL_BASE_URL = _config["external_apis"]["bhl_base_url"]
WORMS_BASE_URL = _config["external_apis"]["worms_base_url"]
GBIF_BASE_URL = _config["external_apis"]["gbif_base_url"]

# Cache constants
CACHE_DIR_NAME = _config["cache"]["dir_name"]
CACHE_SUBDIR_NAME = _config["cache"]["subdir_name"]
CACHE_FILE_NAME = _config["cache"]["file_name"]

# HTTP headers for PBDB API requests
PBDB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; fossil-species-references/1.0; +https://github.com/O957/fossil-species-references)",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}
