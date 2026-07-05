from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chainlit_loads_product_navigation_asset() -> None:
    config = (ROOT / ".chainlit/config.toml").read_text(encoding="utf-8")
    script = (ROOT / "public/product-navigation.js").read_text(encoding="utf-8")

    assert 'custom_js = "/public/product-navigation.js"' in config
    assert "__MEMORY_CHATBOT_CONTROLS__" in script
    assert '"refresh-sidebar"' in script
    assert "setComposerEnabled(productState.active !== false)" in script
    assert "window.location.reload()" in script


def test_product_navigation_has_no_backend_or_model_calls() -> None:
    script = (ROOT / "public/product-navigation.js").read_text(encoding="utf-8")

    assert "fetch(" not in script
    assert "XMLHttpRequest" not in script
    assert "OPENAI" not in script
    assert "api_key" not in script.lower()
