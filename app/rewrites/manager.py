# app/rewrites/manager.py

import os
import json
from datetime import datetime

from app.utils.time_utils import local_timestamp, file_stamp

# =========================================================
# Ensure rewrite directories
# =========================================================

def ensure_rewrite_dirs(output_dir):
    rewrites_dir = os.path.join(
        output_dir,
        "rewrites"
    )

    os.makedirs(
        rewrites_dir,
        exist_ok=True
    )

    return rewrites_dir

# =========================================================
# Metadata registration
# =========================================================

def register_rewrite_version(
    output_dir,
    snapshot_path
):
    """
    Appends rewrite snapshot
    into metadata lifecycle.
    """

    metadata_path = os.path.join(
        output_dir,
        "metadata.json"
    )

    if not os.path.exists(metadata_path):
        return

    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    metadata.setdefault(
        "rewrite_versions",
        []
    )

    relative = os.path.relpath(
        snapshot_path,
        output_dir
    )

    metadata["rewrite_versions"].append(
        relative
    )

    with open(metadata_path, "w") as f:
        json.dump(
            metadata,
            f,
            indent=2
        )

def save_rewrite_snapshot(
    output_dir,
    section,
    before_data,
    after_data
):
    """
    Stores rewrite snapshots.

    Purpose:
    - auditability
    - revert capability
    - rewrite inspection
    """

    rewrites_dir = ensure_rewrite_dirs(
        output_dir
    )

    timestamp = file_stamp()

    filename = (
        f"{section}_rewrite-{timestamp}.json"
    )

    path = os.path.join(
        rewrites_dir,
        filename
    )

    payload = {
        "section": section,
        "created_at": local_timestamp(),

        "before": before_data,
        "after": after_data
    }

    with open(path, "w") as f:
        json.dump(
            payload,
            f,
            indent=2
        )

    register_rewrite_version(
        output_dir,
        path
    )

    return path


def save_resume_snapshot(
    output_dir,
    resume_data,
    source="unknown"
):
    """
    Stores normalized resume snapshots.

    Purpose:
    - edit history
    - rollback support
    - UI state persistence
    - regeneration auditing
    """

    snapshots_dir = os.path.join(
        output_dir,
        "snapshots"
    )

    os.makedirs(
        snapshots_dir,
        exist_ok=True
    )

    timestamp = file_stamp()

    filename = (
        f"resume_snapshot_{timestamp}.json"
    )

    path = os.path.join(
        snapshots_dir,
        filename
    )

    payload = {
        "created_at": local_timestamp(),
        "source": source,
        "resume_data": resume_data
    }

    with open(path, "w") as f:
        json.dump(
            payload,
            f,
            indent=2
        )

    return path