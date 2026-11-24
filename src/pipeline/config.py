"""Where the pipeline's data lives: one place to resolve it.

Precedence, highest first: explicit CLI value, environment variable,
repo-anchored default. Defaults are anchored to the repo root (not the
current working directory), so running from any directory reads the same data.
"""

from __future__ import annotations

import os
from pathlib import Path

# src/pipeline/config.py -> repo root is two levels up from this file's folder.
REPO_ROOT = Path(__file__).resolve().parents[2]
# In a source checkout the demo data sits next to src/. When pip-installed there
# is no such folder, so fall back to ./data in the user's working directory.
_REPO_DATA = REPO_ROOT / "data"
DEFAULT_DATA_DIR = _REPO_DATA if (_REPO_DATA / "profile.json").exists() else Path.cwd() / "data"

ENV_DATA_DIR = "JOBPIPE_DATA_DIR"
ENV_PROFILE = "JOBPIPE_PROFILE"


def resolve_data_dir(cli_value: str | Path | None = None) -> Path:
    """CLI value > $JOBPIPE_DATA_DIR > repo `data/`."""
    if cli_value:
        return Path(cli_value)
    env = os.environ.get(ENV_DATA_DIR)
    return Path(env) if env else DEFAULT_DATA_DIR


def postings_path(data_dir: Path) -> Path:
    return Path(data_dir) / "postings.csv"


def ledger_path(data_dir: Path) -> Path:
    return Path(data_dir) / "resolved_roles.csv"


def raw_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "raw"


def profile_path(data_dir: Path, cli_value: str | Path | None = None) -> Path:
    """CLI --profile > $JOBPIPE_PROFILE > <data_dir>/profile.json."""
    if cli_value:
        return Path(cli_value)
    env = os.environ.get(ENV_PROFILE)
    return Path(env) if env else Path(data_dir) / "profile.json"
