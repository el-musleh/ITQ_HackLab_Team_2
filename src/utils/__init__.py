"""Shared utility helpers for the ITQ Bottle Cap Collector project."""

import os
import yaml


def project_root():
    """Return the absolute path to the project root (the directory containing config.yaml)."""
    # src/utils/__init__.py -> src/utils -> src -> project root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_config(path=None):
    """
    Load the project configuration from config.yaml.

    Args:
        path: Optional explicit path to a YAML config file. If None, reads
            ``config.yaml`` from the project root.

    Returns:
        Parsed configuration dictionary.
    """
    if path is None:
        path = os.path.join(project_root(), 'config.yaml')
    with open(path, 'r') as f:
        return yaml.safe_load(f)


__all__ = ['project_root', 'load_config']
