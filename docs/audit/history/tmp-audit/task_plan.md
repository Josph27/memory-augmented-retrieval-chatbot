# Provider switch and DeepSeek setup

- [x] Inspect configuration and inference clients; verify DeepSeek API requirements.
- [x] Add shared provider resolution, local settings, and both client integrations.
- [x] Add isolated provider/client tests and update setup documentation.
- [x] Run compile, lint, and tests; record limitations.

Keep custom OpenAI-compatible endpoints working; do not change memory architecture.

## Errors
- This branch has no src/settings.py; add a focused provider settings module.
- Full pytest collection blocked by duplicate test_upload module names and the
  existing Chainlit server registration import. Run isolated non-browser tests.
- Repository lint has six existing errors in app.py, src/api_routes.py, and
  tests/test_backend.py; focused lint passes.
