"""Centralized path resolution for both development and PyInstaller builds."""

import sys
from pathlib import Path


def get_app_root() -> Path:
    """
    Get the application root directory.
    - Frozen (PyInstaller): directory containing the executable
    - Development: project root (4 levels up from this file)
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent.parent.parent


def get_data_dir() -> Path:
    """Get the data directory."""
    return get_app_root() / "data"


def get_config_path() -> Path:
    """Get path to config.json."""
    return get_data_dir() / "config" / "config.json"


def get_inputs_dir() -> Path:
    """Get the data/inputs directory."""
    inputs_dir = get_data_dir() / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    return inputs_dir


def get_outputs_dir() -> Path:
    """Get the data/outputs directory."""
    outputs_dir = get_data_dir() / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return outputs_dir


def get_cache_dir() -> Path:
    """Get the .cache directory."""
    cache_dir = get_app_root() / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_metadata_dir() -> Path:
    """Get the .metadata directory."""
    metadata_dir = get_app_root() / ".metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    return metadata_dir
