"""Collection gate: importing application test modules requires OS-runner proof."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
PROOF = Path("/work/isolation-proof.json")
try:
    proof_bytes = PROOF.read_bytes()
    proof = json.loads(proof_bytes)
    assert ROOT == Path("/repo")
    assert os.environ.get("BREAMON_ISOLATED_PROOF") == hashlib.sha256(proof_bytes).hexdigest()
    assert proof["verified_before_imports"] and all(proof["canaries"].values())
    assert proof["network_namespace"] == os.readlink("/proc/self/ns/net")
    assert proof["mount_namespace"] == os.readlink("/proc/self/ns/mnt")
    assert proof["host_network_namespace"] != proof["network_namespace"]
    assert proof["host_mount_namespace"] != proof["mount_namespace"]
    assert proof["source_readonly"] is True
except (OSError, ValueError, KeyError, AssertionError) as exc:
    raise pytest.UsageError(
        "Collection blocked before test imports: use python3 scripts/run_isolated_tests.py "
        "--label initial --group offline-unit (or --group offline-integration). "
        "Verified OS isolation and pre-import canaries are required."
    ) from exc

REGISTRY = json.loads((ROOT / "docs/audit/stage5/groups.json").read_text())
GROUPS = proof["groups"]
ALLOWED = set()
for group in GROUPS:
    entry = REGISTRY["groups"][group]
    if not entry["enabled"]:
        raise pytest.UsageError(f"Disabled test group: {group}: {entry['reason']}")
    ALLOWED.update(entry["files"])


def pytest_configure(config):
    # pytest can bypass ignore hooks for explicit file arguments. Reject those here.
    for argument in config.args:
        candidate = Path(str(argument).split("::", 1)[0]).resolve()
        if candidate.is_file():
            try:
                name = candidate.relative_to(ROOT).as_posix()
            except ValueError as exc:
                raise pytest.UsageError(
                    "Tests outside the isolated registry are forbidden"
                ) from exc
            if name not in ALLOWED:
                raise pytest.UsageError(f"File absent from enabled group registry: {name}")


def pytest_ignore_collect(collection_path: Path, config):
    """Deny unregistered files *before* module import, including explicit paths."""
    path = Path(collection_path).resolve()
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        return True
    if path.is_dir():
        return not any(p.startswith(relative + "/") for p in ALLOWED)
    if path.suffix == ".py" and path.name != "conftest.py":
        return relative not in ALLOWED
    return None


def pytest_collection_modifyitems(config, items):
    selected, excluded = [], []
    for item in items:
        nodeid = item.nodeid.removeprefix("/repo/")
        file = Path(str(item.path)).resolve().relative_to(ROOT).as_posix()
        if file not in ALLOWED or nodeid in REGISTRY["excluded_nodes"]:
            excluded.append(item)
        else:
            group = next(g for g in GROUPS if file in REGISTRY["groups"][g]["files"])
            item.add_marker(
                getattr(pytest.mark, REGISTRY["groups"][group]["category"].replace("-", "_"))
            )
            selected.append(item)
    items[:] = selected
    if excluded:
        config.hook.pytest_deselected(items=excluded)
