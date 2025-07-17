"""Common utility functions used across the codebase to eliminate duplication."""

import os
import shutil
from typing import Any, Callable, List


def deduplicate_by_representation(
    items: List[Any], get_representation: Callable[[Any], Any]
) -> List[Any]:
    """
    Remove duplicates from a list based on a representation function.

    Args:
        items: List of items to deduplicate
        get_representation: Function that returns a hashable representation of an item

    Returns:
        List with duplicates removed, preserving order
    """
    seen = set()
    result = []
    for item in items:
        rep = get_representation(item)
        if rep not in seen:
            seen.add(rep)
            result.append(item)
    return result


def find_ripgrep() -> str:
    """Find ripgrep executable in common locations."""
    rg_path = shutil.which("rg")
    if not rg_path:
        # Try common locations
        possible_paths = [
            "/usr/local/bin/rg",
            "/opt/homebrew/bin/rg",
            # Add more common ripgrep paths as needed
        ]
        for path in possible_paths:
            if os.path.exists(path):
                rg_path = path
                break
    return rg_path
