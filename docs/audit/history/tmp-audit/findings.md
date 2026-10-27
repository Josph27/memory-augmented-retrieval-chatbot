# Findings

- AppConfig and LangMemBackendConfig independently read OPENAI_* and MODEL_NAME.
- Current branch uses the OpenAI SDK for chat and ChatOpenAI for LangMem.
- local_settings.py is already ignored by Git.
- DeepSeek documents https://api.deepseek.com and deepseek-flash.
- DeepSeek tool choice required/named is unsupported in thinking mode; use
  extra_body={"thinking": {"type": "disabled"}} for chat and memory clients.
- Sources: https://api-docs.deepseek.com/quick_start/agent_integrations/
  and https://api-docs.deepseek.com/api/create-chat-completion/.
