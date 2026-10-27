# PURGE1 batch1 — approved diagram artifact

DEC016 / TASK15. Worktree: /home/josph/.codex/worktrees/audit-main/repo; branch codex/audit-main. Starting commit:3a3ad03e5fb33b23c56aa5f36e49c1f2e413bf67. Starting working tree clean; no unrelated changes to preserve. Original worktree/stashes untouched.

## Scope and consumer evidence

Deleted only docs/mermaid-diagram-2026-07-15-021559.png: **3,063,514bytes**. Original Git blob7ac3a06708d28a20ed7e10006efbfa5f5cd74eb9; SHA256324fca1c4ad9c58eaea58f18e95def6cb27fa740ec4df30fe5c9f3434c667b44. This reduces checked-out asset size, not Git history storage.

Retained [editable Mermaid source](../system-component-map.mmd),6062bytes, SHA2569a5b83eaa7dea417e9b520a8e6746b6113d7c4d2145c099125914b144d0fbe95, byte-for-byte unchanged. No claim of exact image/layout reproduction. All other assets, code, tests and evaluation capabilities remain unchanged.

Rechecked tracked text for full filename/path, timestamp/stem variants and source name; inspected code/documentation/configuration/packaging/scripts/asset rules. The only PNG references were historical audit inventories/manifests and the previous Stage5 proposal. No active reference or docs-PNG processing glob found. pyproject.toml disables project packaging; Vite/Chainlit use their frontend/public assets, not this docs image. Document loader supports txt/md/pdf, not png. No tracked documentation-build/asset-copy configuration consumes this image. Historical references remain provenance and were not rewritten.

## Validation

- Exactly one non-document deletion; documentation changes limited to current status, decisions/ledger and this execution record.
- Retained source exists with the same hash; all other existing assets/application/tests/evaluations and historical evidence unchanged.
- Rechecked references and local Markdown links, and ran git diff --check. No broken link introduced by the removal.
- Application tests not rerun for an unreferenced artifact; prior Stage5 results remain dated evidence, not newly executed checks. No live inference.

## Recovery without history rewriting

From the active worktree, restore the exact former blob into the working tree:

```bash
git restore --source=3a3ad03e5fb33b23c56aa5f36e49c1f2e413bf67 -- docs/mermaid-diagram-2026-07-15-021559.png
```

This restores the file locally. To retain it in a later revision, git add that path and commit the restoration. Earlier history remains available; no reset, squash or force-push needed. The command intentionally targets only the removed file.
