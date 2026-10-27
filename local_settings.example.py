"""Copy to local_settings.py; this local file is ignored by Git."""

PROVIDER = "deepseek"  # deepseek | custom
DEEPSEEK_API_KEY = ""  # Paste your API key in local_settings.py only.
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"

# For another OpenAI-compatible service, select custom and configure
# OPENAI_API_KEY, OPENAI_BASE_URL, and MODEL_NAME in .env.
