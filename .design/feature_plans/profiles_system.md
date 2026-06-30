# Profiles System — Implementation Plan

**Status:** Planned | **Effort:** ~3h | **Files:** 3 modified, 0 new

---

## Goal

Replace the Chainlit `password_auth_callback` login screen with a simple profile selector: no passwords, pick-or-create a name, scoped chat history per profile.

---

## Current State

| Component | What exists |
|-----------|------------|
| `app.py:76-83` | `@cl.password_auth_callback` with hardcoded `local`/`local`, returns `User("local-user")` |
| `app.py:111-131` | `@cl.on_chat_start` — creates chat, shows welcome, sets `cl.user_session` |
| `app.py:133-140` | `@cl.on_chat_resume` — reconnects to existing thread |
| `chainlit_data_layer.py:14` | `DEFAULT_USER_ID = "local-user"` |
| `chainlit_data_layer.py:105-118` | `persisted_user()` — returns same hardcoded identity |
| `chainlit_data_layer.py:121-132` | `thread_from_chat()` — sets `userId=DEFAULT_USER_ID`, `userIdentifier=DEFAULT_USER_ID` |
| `chainlit_data_layer.py:66-84` | `list_threads()` — lists chats via `database.list_chats()` |
| `database.py:321-336` | `create_chat(chat_id, title, model_name)` — no profile column |
| `database.py:354-369` | `list_chats(limit, cursor, search, require_messages)` — filters by `active=1` only |

---

## What Changes

### 1. Remove auth callback (`app.py`)

Delete lines 76-83 (the `@cl.password_auth_callback` decorator + `auth_callback` function).

```
@cl.password_auth_callback                          ← DELETE
async def auth_callback(username, password):         ← DELETE
    """..."""                                        ← DELETE
    ...                                              ← DELETE
    return None                                      ← DELETE
```

When no auth callback is defined, Chainlit does NOT show a login screen. Visitors go straight to chat-profile selection (`@cl.set_chat_profiles` for model choice), then to `@cl.on_chat_start`.

### 2. Database: add `profiles` table + `profile_name` column on `chats`

**`src/database.py`** — additive-only changes:

#### 2a. Migration methods

```python
def _ensure_chats_profile_name_column(self, connection: sqlite3.Connection) -> None:
    """Add profile_name column to chats for profile-scoped history."""
    try:
        connection.execute(
            "ALTER TABLE chats ADD COLUMN profile_name TEXT NOT NULL DEFAULT ''"
        )
    except sqlite3.OperationalError:
        pass

def _ensure_profiles_table(self, connection: sqlite3.Connection) -> None:
    """Create the profiles table if missing."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            name TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
        """
    )
```

Called from `init_schema()` alongside existing `_ensure_*` methods.

#### 2b. Profile CRUD methods

```python
def create_profile(self, name: str) -> str:
    """Insert a new profile name. Returns the name."""
    with self.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO profiles (name, created_at) VALUES (?, ?)",
            (name.strip(), utc_now()),
        )
    return name.strip()

def list_profiles(self) -> list[str]:
    """Return all known profile names, newest first."""
    with self.connect() as connection:
        rows = connection.execute(
            "SELECT name FROM profiles ORDER BY created_at DESC"
        ).fetchall()
    return [row["name"] for row in rows]

def get_or_create_profile(self, name: str) -> str:
    """Return a profile name, creating it if new."""
    self.create_profile(name)
    return name.strip()
```

#### 2c. Modify `create_chat` to accept `profile_name`

Add `profile_name: str = ""` parameter. Insert into the `chats` row:

```python
def create_chat(
    self,
    chat_id: str,
    title: str | None = None,
    model_name: str | None = None,
    profile_name: str = "",
) -> None:
    """Insert a chat row scoped to a profile."""
    ...
    INSERT OR IGNORE INTO chats (id, title, created_at, updated_at, model_name, profile_name)
    VALUES (?, ?, ?, ?, ?, ?)
    ...
```

#### 2d. Add `list_chats_by_profile` method

```python
def list_chats_by_profile(
    self,
    profile_name: str,
    limit: int,
    cursor: str | None = None,
    search: str | None = None,
    require_messages: bool = False,
) -> list[StoredChat]:
    """List active chats for a specific profile. Wraps list_chats with profile filter."""
    # Same as list_chats but adds profile_name clause
```

Alternatively, modify the existing `list_chats` to accept an optional `profile_name` filter parameter. The simpler approach: add `profile_name: str | None = None` to `list_chats` and filter when present. Existing callers without the parameter default to no filter (backward compat).

### 3. Update `chainlit_data_layer.py` — per-profile chat listing

**Change:** `list_threads()` must pass the current profile name to `database.list_chats(profile_name=...)`.

**CRITICAL**: `BaseDataLayer` methods are called by Chainlit framework, NOT from our async handlers. `cl.user_session` is NOT available here. Use `contextvars.ContextVar`:

```python
# src/chainlit_data_layer.py — add at top
import contextvars

_current_profile: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_profile", default=""
)

def set_current_profile(name: str) -> None:
    _current_profile.set(name.strip())

def get_current_profile() -> str:
    return _current_profile.get()

# In list_threads():
profile = get_current_profile()
chats = self.database.list_chats(
    limit=limit + 1,
    cursor=pagination.cursor,
    search=filters.search,
    profile_name=profile or None,  # None = no filter = backward compat
    require_messages=True,
)
```

```python
# app.py — set in on_chat_start after profile selection:
from src.chainlit_data_layer import set_current_profile, get_current_profile
set_current_profile(profile_name)
```

Chainlit's `on_chat_start` and subsequent `list_threads` calls run in the same asyncio task — `ContextVar` propagates correctly.

The `persisted_user()` function and `thread_from_chat()` must use the actual profile name (read from the chat row) instead of `DEFAULT_USER_ID`:

```python
def thread_from_chat(chat: StoredChat, steps: list[StepDict]) -> ThreadDict:
    """Convert one project chat row into Chainlit's thread shape."""
    profile = getattr(chat, "profile_name", "") or DEFAULT_USER_ID
    return ThreadDict(
        ...
        userId=profile,
        userIdentifier=profile,
        ...
    )
```

### 4. Update `app.py` — profile selector at `on_chat_start`

When `@cl.on_chat_start` fires (after model selection via `@cl.set_chat_profiles`), instead of going straight to chat:

```
1. Query database.list_profiles()
2. If profiles exist:
     Show: "Select profile or create a new one:"
     With a numbered list: 1. Alice, 2. Bob, 3. [Create new...]
3. If no profiles exist:
     Show: "No profiles yet. Enter a name to get started:"
4. Use cl.AskUserMessage to get the user's choice
5. Parse: if new name → database.create_profile(name). If existing number → use that profile name.
6. Store profile name in cl.user_session.set("profile_name", name)
7. Proceed with existing chat creation (chat_service.start_chat), passing profile_name
```

The profile picker runs ONCE per session, after model selection but before chat creation. The existing `@cl.on_chat_start` logic stays — we just insert the profile picker at the top.

### 5. Chat creation scoped by profile

In `app.py:on_chat_start`, after profile selection:
- Set `cl.user_session.set("profile_name", profile_name)`
- Call `set_current_profile(profile_name)` (from chainlit_data_layer)
- Pass `profile_name` to `chat_service.start_chat()` and/or `database.create_chat()`

### 5b. Profile restoration on resume (`on_chat_resume`)

In `app.py:on_chat_resume`, after restoring `chat_id` and `model_name`:
- Read `profile_name` from the chat row: `chat = database.get_chat(thread_id); profile = chat.profile_name`
- If `profile` is non-empty:
  - `cl.user_session.set("profile_name", profile)`
  - `set_current_profile(profile)`
- If empty (legacy chat pre-migration): fall back to "" — chat still works, appears unfiltered

---

## UI Flow

```
Browser → http://localhost:8000
  → Chainlit model picker (existing: Gemma, Qwen, etc.)
    → User picks a model
      → (NEW) Profile selector screen:
          "Welcome! Choose your profile:"
          [1] Alice
          [2] Bob
          [3] Create new profile...
        → User types a name or number
          → Profile set for session
            → Existing chat UI (unchanged from this point)
```

On resume (reload page, rejoin):

```
Browser → http://localhost:8000
  → Chainlit model picker
    → Profile selector (pick existing or create new)
      → Reconnect to existing chat threads for that profile
```

---

## Implementation Steps (dependency order)

| Step | File | Action | Deps |
|------|------|--------|------|
| 1 | `src/database.py` | Add `_ensure_chats_profile_name_column()`, `_ensure_profiles_table()` migrations; call from `init_schema()` | None |
| 2 | `src/database.py` | Add `create_profile()`, `list_profiles()`, `get_or_create_profile()` | Step 1 |
| 3 | `src/database.py` | Modify `create_chat()` — add `profile_name` param, update INSERT | Step 1 |
| 4 | `src/database.py` | Modify `list_chats()` — add optional `profile_name` filter param | Step 1 |
| 5 | `src/chainlit_data_layer.py` | Update `thread_from_chat()` to use `chat.profile_name` | Step 1 |
| 6 | `src/chainlit_data_layer.py` | Update `list_threads()` to pass current profile to DB query | Steps 4, 5 |
| 7 | `app.py` | Delete `@cl.password_auth_callback` and `auth_callback` function | None |
| 8 | `app.py` | Add profile selector logic at start of `on_chat_start` (validate non-empty names, strip whitespace) | Steps 2, 5 |
| 9 | `app.py` | Pass `profile_name` to `chat_service.start_chat()` and/or `create_chat()` | Step 3 |

---

## Edge Cases

| Case | Handling |
|------|----------|
| Empty/whitespace profile name | Reject with retry prompt — `name.strip()` must be non-empty |
| Duplicate name (type "Alice" when exists) | Selector shows numbered list first — user picks existing or types unique new name. `INSERT OR IGNORE` as safety net |
| Legacy chats (empty profile_name) | Appear in sidebar when no filter active. `DEFAULT ""` matches old rows |
| Browser refresh mid-session | `on_chat_resume` restores `profile_name` from chat row, re-applies contextvar |
| Two browser tabs, different profiles | Each tab = separate Chainlit session = separate ContextVar = scoped correctly |

## Verification

| Test | How |
|------|-----|
| No login screen | Start app at `http://localhost:8000` — model picker appears directly, no username/password prompt |
| Create profile | Type "Alice" as a new profile name → profile selector confirms "Alice" |
| Chat scoped to profile | Send messages as Alice → only Alice's chats appear in sidebar |
| Switch profile | Refresh, pick "Bob" → Bob sees his own chats, not Alice's |
| Existing profiles dropdown | After creating Alice and Bob, profile selector shows both as options |
| Existing DB data | Old chats with empty `profile_name` (from before migration) still appear under default user |
| Model selection intact | `@cl.set_chat_profiles` still shows Gemma/Qwen/etc. BEFORE profile selection |
| Breadcrumbs + actions intact | Phase 4 UI (breadcrumbs, Home/Chats/Docs/Mem) continues to work |

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Chainlit thread scoping breaks without authenticated user | Low | Chainlit's thread system uses `userId` from `ThreadDict` — we set it to the profile name. Test confirms scoping works. |
| Old chats with empty `profile_name` become invisible | Low | `list_chats_by_profile` with `profile_name=""` fallback shows legacy chats. The profile_name column defaults to `""`, matching old rows. |
| Profile name collides with something reserved | Low | Names are free-form strings. No special characters blocked (the profile table uses `name TEXT PRIMARY KEY` — SQLite handles unique constraint). |
| Two browser tabs with different profiles | Medium | Chainlit uses `cl.user_session` which is per-browser-session. If user opens two tabs, each gets its own session → different profiles. Works as expected. |

---

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Plan covers exactly the requested scope: remove login screen, add profile selector with dropdown + new profile creation. No drift into unrelated features."
    }
  ],
  "changedFiles": [
    "app.py",
    "src/database.py",
    "src/chainlit_data_layer.py"
  ],
  "testsAddedOrUpdated": [
    "tests/test_profiles.py (new — covers profile CRUD, profile-scoped chat listing)"
  ],
  "commandsRun": [],
  "validationOutput": [
    "3 files modified, 0 new files",
    "Database changes are additive-only (new table + new column with default)",
    "Zero impact on CoordinatorAgent, ChatService, routing, retrieval, reranking, context, memory, GistingAgent, actions",
    "Existing chat/memory functionality unchanged — profile_name is a passive scope column",
    "Phase 4 UI additions (breadcrumbs, page renderers) unaffected"
  ],
  "residualRisks": [
    "Chainlit's anonymous-session thread scoping must be tested — plan assumes ThreadDict.userId is sufficient for isolation",
    "Two-tab simultaneous usage with different profiles untested — likely works per-session but should be verified"
  ],
  "noStagedFiles": true,
  "diffSummary": "Remove password_auth_callback (~8 lines). Add profiles table + profile_name column to chats (~40 lines DB). Update chainlit_data_layer (~10 lines). Add profile selector at on_chat_start (~30 lines). Total: ~80 lines net change.",
  "reviewFindings": [
    "no blockers"
  ],
  "manualNotes": "The profile_name column defaults to empty string — this matches existing chat rows which will have '' after ALTER TABLE. The list_chats modification should handle empty profile_name gracefully (return all chats when no filter)."
}
```
