# Progress

- Initial checkout clean; read configuration and memory client factories.
- Verified DeepSeek API requirements against official documentation.
- No API key supplied; live inference verification will remain pending.
- Added shared provider resolution, DeepSeek request options, local settings
  template and prepared ignored local file; preserved legacy custom env values.
- Updated chat resume model selection and README; removed university example URL.
- Initial focused regression run: 29 passed, one dependency deprecation warning.
- Compile and diff whitespace checks pass. Full pytest collection has two errors
  (duplicate upload test name, Chainlit server import); full lint has six errors
  outside the changed provider code. These are left for the baseline audit.
- Final focused regression run: 79 passed, one dependency deprecation warning.
  Includes mock HTTP serialization for the OpenAI and LangChain clients, local
  settings/env precedence, missing keys, legacy config, and resumed chat models.
- Full compileall and git diff --check pass. Verified local_settings.py is ignored.
- This branch has no startup.py; README uses the Chainlit launch command.
- Live DeepSeek authentication and end-to-end memory extraction require the user's key.
