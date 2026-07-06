from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from src.database import Database


ROOT = Path(__file__).resolve().parents[2]
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


@dataclass
class BrowserHarness:
    page: Page
    database: Database
    model_events: Path
    artifacts: Path


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Chainlit exited before readiness: {process.returncode}")
        try:
            with urlopen(url, timeout=0.2):  # noqa: S310 - fixed localhost URL
                return
        except Exception:
            time.sleep(0.05)
    raise RuntimeError("Chainlit did not become ready")


def _seed(database: Database) -> None:
    for chat_id, title, active in (
        ("active-a", "Active Alpha", True),
        ("active-b", "Active Beta", True),
        ("active-c", "Active Gamma", True),
        ("ended-a", "Ended Alpha", False),
        ("ended-b", "Ended Beta", False),
    ):
        database.create_chat(chat_id, title=title)
        database.save_message(chat_id, "user", f"{title} question")
        database.save_message(chat_id, "assistant", f"{title} answer")
        if not active:
            database.mark_chat_inactive(chat_id)


def _login(page: Page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded")
    page.get_by_label("Email address").fill("local")
    page.get_by_label("Password").fill("local")
    page.get_by_role("button", name="Sign In").click()
    page.locator("#memory-chatbot-home").wait_for(state="visible")


@pytest.fixture
def browser_harness(tmp_path: Path, request: pytest.FixtureRequest):
    if not CHROME.exists():
        pytest.skip(f"local Chrome executable unavailable: {CHROME}")
    database_path = tmp_path / "chat.db"
    database = Database(database_path)
    _seed(database)
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    event_path = tmp_path / "model-events.jsonl"
    artifacts = tmp_path / "browser-failures"
    artifacts.mkdir()
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "DATABASE_PATH": str(database_path),
        "LANGCHAIN_CHROMA_PERSIST_DIR": str(tmp_path / "chroma"),
        "CHAINLIT_LOCAL_USERNAME": "local",
        "CHAINLIT_LOCAL_PASSWORD": "local",
        "PRODUCT_BEHAVIOR_MODEL_EVENT_PATH": str(event_path),
    }
    process = subprocess.Popen(
        [
            "uv",
            "run",
            "chainlit",
            "run",
            "tests/e2e/product_behavior_chainlit_app.py",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    playwright = sync_playwright().start()
    browser: Browser | None = None
    context = None
    try:
        _wait_for_server(url, process)
        browser = playwright.chromium.launch(
            executable_path=str(CHROME),
            headless=True,
        )
        context = browser.new_context()
        context.tracing.start(screenshots=True, snapshots=True)
        page = context.new_page()
        _login(page, url)
        harness = BrowserHarness(page, database, event_path, artifacts)
        yield harness
        if getattr(request.node, "rep_call", None) and request.node.rep_call.failed:
            page.screenshot(path=artifacts / f"{request.node.name}.png", full_page=True)
            context.tracing.stop(path=artifacts / f"{request.node.name}.zip")
        else:
            context.tracing.stop()
    finally:
        if context is not None:
            context.close()
        if browser is not None:
            browser.close()
        playwright.stop()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _open_thread(page: Page, title: str) -> None:
    thread = page.get_by_text(title, exact=True)
    thread.wait_for(state="visible")
    thread.click()
    page.get_by_text(f"{title} question", exact=True).wait_for(state="visible")


def _toolbar_button(page: Page, label: str):
    toolbar = page.get_by_role("toolbar", name="Chat lifecycle controls")
    toolbar.wait_for(state="visible")
    return toolbar.get_by_role("button", name=label)


def _wait_for(predicate, *, timeout: float = 10.0) -> None:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("observable persisted state did not change before timeout")


def test_pb_nav_001_home_is_message_free(browser_harness: BrowserHarness) -> None:
    before = sum(
        browser_harness.database.message_count(chat_id)
        for chat_id in ("active-a", "active-b", "active-c", "ended-a", "ended-b")
    )
    assert browser_harness.page.locator("#memory-chatbot-home").is_visible()
    assert not browser_harness.model_events.exists()
    after = sum(
        browser_harness.database.message_count(chat_id)
        for chat_id in ("active-a", "active-b", "active-c", "ended-a", "ended-b")
    )
    assert after == before


def test_pb_nav_003_ended_chats_visible_and_read_only(
    browser_harness: BrowserHarness,
) -> None:
    _open_thread(browser_harness.page, "Ended Alpha")
    assert browser_harness.page.get_by_text("Ended Beta", exact=True).is_visible()
    assert browser_harness.page.locator("textarea").is_disabled()
    assert not browser_harness.model_events.exists()


def test_pb_nav_008_reload_restores_navigation(
    browser_harness: BrowserHarness,
) -> None:
    _open_thread(browser_harness.page, "Ended Alpha")
    browser_harness.page.reload(wait_until="domcontentloaded")
    browser_harness.page.get_by_text("Ended Alpha question", exact=True).wait_for(
        state="visible"
    )
    assert browser_harness.page.get_by_text("Active Alpha", exact=True).is_visible()
    assert browser_harness.page.get_by_text("Ended Beta", exact=True).is_visible()


def test_pb_life_001_new_chat_persists_and_opens(
    browser_harness: BrowserHarness,
) -> None:
    before = len(browser_harness.database.list_chats(limit=100))
    new_chat_button = browser_harness.page.locator("#new-chat-button")
    new_chat_button.click()
    browser_harness.page.get_by_role(
        "toolbar",
        name="Chat lifecycle controls",
    ).wait_for(state="visible")
    after = len(browser_harness.database.list_chats(limit=100))
    assert after == before + 1


def test_pb_life_005_end_chat_does_not_render_navigation(
    browser_harness: BrowserHarness,
) -> None:
    _open_thread(browser_harness.page, "Active Alpha")
    _toolbar_button(browser_harness.page, "End Chat").click()
    _wait_for(lambda: not browser_harness.database.is_chat_active("active-a"))
    browser_harness.page.locator("body[data-memory-chat-active='false']").wait_for(
        state="attached"
    )
    transcript = browser_harness.page.locator("main").inner_text()
    assert "Active Beta" not in transcript
    assert "Ended Beta" not in transcript


def test_pb_life_006_ended_history_remains_readable(
    browser_harness: BrowserHarness,
) -> None:
    _open_thread(browser_harness.page, "Ended Alpha")
    assert browser_harness.page.get_by_text("Ended Alpha answer", exact=True).is_visible()
    assert browser_harness.page.locator("textarea").is_disabled()


def test_pb_life_009_fork_creates_and_opens_independent_chat(
    browser_harness: BrowserHarness,
) -> None:
    _open_thread(browser_harness.page, "Active Beta")
    before = len(browser_harness.database.list_chats(limit=100))
    previous_url = browser_harness.page.url
    _toolbar_button(browser_harness.page, "Fork Chat").click()
    _wait_for(
        lambda: len(browser_harness.database.list_chats(limit=100)) == before + 1
    )
    browser_harness.page.wait_for_function(
        "(previous) => window.location.href !== previous",
        arg=previous_url,
    )
    browser_harness.page.get_by_text("Active Beta question", exact=True).wait_for(
        state="visible"
    )
    assert len(browser_harness.database.list_chats(limit=100)) == before + 1


def test_product_shell_visual_cleanup_and_toolbar_state(
    browser_harness: BrowserHarness,
) -> None:
    page = browser_harness.page
    home = page.locator("#memory-chatbot-home")
    assert home.get_by_role("heading", name="Memory Retrieval Chatbot").is_visible()
    assert home.get_by_text("Select a chat or start a new one.", exact=True).is_visible()
    assert not page.get_by_text("Gemma 4 31B", exact=True).is_visible()
    assert not page.get_by_text("Default TUM AIR AKG model", exact=False).is_visible()
    assert not page.get_by_text("google/gemma-4-31B-it", exact=False).is_visible()
    assert not page.get_by_text("Chainlit", exact=True).is_visible()
    assert page.get_by_role(
        "toolbar",
        name="Chat lifecycle controls",
    ).count() == 0
    assert "· active" not in page.locator("body").inner_text().lower()
    broken_images = page.locator("header img, #memory-chatbot-home img").evaluate_all(
        "(images) => images.filter((image) => image.complete && image.naturalWidth === 0)"
        ".map((image) => image.getAttribute('src'))"
    )
    assert broken_images == []

    _open_thread(page, "Active Alpha")
    toolbar = page.get_by_role("toolbar", name="Chat lifecycle controls")
    toolbar.wait_for(state="visible")
    assert toolbar.count() == 1
    assert toolbar.get_by_role("button").all_inner_texts() == [
        "End Chat",
        "Fork Chat",
        "New Chat",
        "Home",
    ]
    assert toolbar.evaluate("(element) => Boolean(element.closest('main'))")
    assert toolbar.evaluate(
        "(element) => getComputedStyle(element).position !== 'fixed'"
    )
    assert toolbar.get_attribute("data-mount") == "composer"
    header = page.locator("header")
    if header.count():
        assert toolbar.bounding_box()["y"] >= (  # type: ignore[index]
            header.bounding_box()["y"] + header.bounding_box()["height"]  # type: ignore[index]
        )

    _open_thread(page, "Ended Alpha")
    toolbar = page.get_by_role("toolbar", name="Chat lifecycle controls")
    assert toolbar.count() == 1
    assert toolbar.get_by_role("button").all_inner_texts() == [
        "Fork Chat",
        "New Chat",
        "Home",
    ]
    assert toolbar.get_by_role("button", name="End Chat").count() == 0

    page.reload(wait_until="domcontentloaded")
    page.get_by_text("Ended Alpha question", exact=True).wait_for(state="visible")
    assert page.get_by_role(
        "toolbar",
        name="Chat lifecycle controls",
    ).count() == 1
    _toolbar_button(page, "Home").click()
    page.locator("#memory-chatbot-home").wait_for(state="visible")
    assert page.get_by_role(
        "toolbar",
        name="Chat lifecycle controls",
    ).count() == 0


def test_pb_doc_002_indexing_finishes_before_answer(
    browser_harness: BrowserHarness,
    tmp_path: Path,
) -> None:
    browser_harness.page.locator("#new-chat-button").click()
    browser_harness.page.get_by_role(
        "toolbar",
        name="Chat lifecycle controls",
    ).wait_for(state="visible")
    upload = tmp_path / "report.txt"
    upload.write_text("The result is deterministic.", encoding="utf-8")
    browser_harness.page.locator("#upload-button-input").set_input_files(str(upload))
    composer = browser_harness.page.locator("textarea")
    composer.fill("What is the result?")
    composer.press("Enter")
    browser_harness.page.get_by_text(
        "Deterministic answer: What is the result?",
        exact=True,
    ).wait_for(state="visible")
    events = [
        json.loads(line)
        for line in browser_harness.model_events.read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["document_statuses"] == ["Ready"]
