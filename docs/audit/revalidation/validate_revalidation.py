"""Check revalidation evidence completeness without importing application/test code."""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import re
import subprocess
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-original", action="store_true")
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    repo = folder.parents[2]
    manifest = json.loads((folder / "coverage-manifest.json").read_text())
    required = {"product-source-config-doc-test", "evaluation-input-contract", "asset-metadata"}
    rows = {r["path"]: r for r in manifest["records"] if r["scope"] in required}
    file_report = (folder / "file-assessments.md").read_text()
    observed = set(re.findall(r"^\| `([^`]+)` \|", file_report, re.M))
    assert not rows.keys() - observed, sorted(rows.keys() - observed)
    for path, row in rows.items():
        if row["new_sha256"]:
            assert sha(repo / path) == row["new_sha256"], f"assessed-source drift: {path}"
        else:
            assert not (repo / path).exists(), f"old-only path unexpectedly restored: {path}"
    history = repo / "docs/audit/history/tmp-audit"
    for name, digest in json.loads((history / "snapshot-sha256.json").read_text()).items():
        assert sha(history / name) == digest, f"historical evidence changed: {name}"
    expected_ts = {r["old_test_id"] for r in manifest["records"] if r.get("old_test_id")}
    ts_text = (folder / "test-inventory.md").read_text()
    assert expected_ts <= set(re.findall(r"\bTS-\d+\b", ts_text))
    for name, prefix, count in [
        ("findings-register.md", "AUD", 20),
        ("findings-register.md", "TSA", 13),
        ("workflow-reconciliation.md", "WF", 16),
    ]:
        text = (folder / name).read_text()
        assert {f"{prefix}-{i:02}" for i in range(1, count + 1)} <= set(
            re.findall(r"\b" + prefix + r"-\d+\b", text)
        )
    for name in [
        "static-assessment.md",
        "test-assessment.md",
        "findings-register.md",
        "workflow-reconciliation.md",
        "test-inventory.md",
        "file-assessments.md",
    ]:
        text = (folder / name).read_text()
        assert "tokens truncated" not in text and "truncated output" not in text, name
    results = json.loads((folder / "execution-results.json").read_text())
    seen = {}
    for cohort in results["cohorts"]:
        assert all(cohort["canaries"].values()) and not cohort["collection_errors"]
        assert collections.Counter(x["outcome"] for x in cohort["records"]) == cohort["counts"]
        if cohort["configuration"] == "deterministic":
            for record in cohort["records"]:
                assert record["nodeid"] not in seen
                seen[record["nodeid"]] = record["outcome"]
    assert dict(collections.Counter(seen.values())) == results["unique_deterministic_counts"]
    for record in json.loads((folder / "executed-inputs/verified-input-index.json").read_text()):
        assert sha(folder / "executed-inputs" / record["exact_file"]) == record["sha256"]
    cohorts = json.loads((folder / "execution-cohorts.json").read_text())
    selected = {p for v in cohorts.values() for p in v["files"]}
    unexecuted = {r["path"] for r in json.loads((folder / "unexecuted-checks.json").read_text())}
    current_python_tests = {
        r["path"]
        for r in manifest["records"]
        if r["path"].startswith("tests/") and r["path"].endswith(".py") and r["new_sha256"]
    }
    assert current_python_tests <= selected | unexecuted
    assert all(f"`{path}`" in ts_text for path in current_python_tests)
    assert "`evals/test_short_term_memory.py`" in ts_text
    links = 0
    for f in folder.rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", f.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            assert (f.parent / target.split("#")[0]).exists(), (f, target)
            links += 1
    for name in ["run_existing_checks.py", "launch_existing_checks.py", "validate_revalidation.py"]:
        compile(ast.parse((folder / name).read_text(), filename=name), name, "exec")
    original_checked = False
    if args.check_original:
        backup = Path(
            "/home/josph/.codex/visualizations/2026/10/27/01a17c90-af7a-73e3-a898-6d83405fa321/breamon-recovery-20261027"
        )
        saved = json.loads((backup / "manifest.json").read_text())
        original = Path(saved["source_root"])
        for name, item in saved["files"].items():
            assert sha(original / name) == item["sha256"]

        def git(*cmd: str) -> str:
            return subprocess.check_output(["git", *cmd], cwd=original, text=True)

        assert git("rev-parse", "HEAD").strip() == saved["source_head"]
        assert (
            git("status", "--porcelain=v1", "--untracked-files=all")
            == (backup / "status.txt").read_text()
        )
        assert git("stash", "list", "--format=%gd %H %gs") == (backup / "stashes.txt").read_text()
        assert sha(backup / "files.tar.gz") == saved["archive_sha256"]
        runtime = json.loads((backup / "revalidation-runtime-manifest.json").read_text())
        assert sha(Path(runtime["archive"])) == runtime["archive_sha256"]
        original_checked = True
    print(
        json.dumps(
            {
                "relevant_paths": len(rows),
                "historical_test_IDs": len(expected_ts),
                "current_python_test_sources": len(current_python_tests),
                "unique_deterministic_counts": results["unique_deterministic_counts"],
                "local_links_checked": links,
                "historical_snapshot_unchanged": True,
                "assessed_product_hashes_unchanged": True,
                "original_backup_status_stashes_checked": original_checked,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
