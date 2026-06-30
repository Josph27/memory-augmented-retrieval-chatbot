#!/usr/bin/env python
"""Start the Chainlit application server."""

import sys, os, logging, asyncio, uvicorn, time

# Disable telemetry
os.environ["LITERAL_API_KEY"] = ""
os.environ["TRACELOOP_TRACING_ENABLED"] = "false"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
    force=True,
)

t0 = time.time()
print(f"[{time.strftime('%H:%M:%S')}] Importing chainlit...", flush=True)

from chainlit.cli import check_file, load_module, assert_app
from chainlit.config import config
from chainlit.server import app as chainlit_app
from chainlit.auth import ensure_jwt_secret
from chainlit.markdown import init_markdown
from chainlit.cache import init_lc_cache

print(f"[{time.strftime('%H:%M:%S')}] Imports done ({time.time() - t0:.0f}s)", flush=True)

config.run.module_name = "app.py"
config.run.host = "0.0.0.0"
config.run.port = 8000
check_file("app.py")
load_module("app.py")
ensure_jwt_secret()
assert_app()
init_markdown(config.root)
init_lc_cache()

print(f"[{time.strftime('%H:%M:%S')}] Setup done ({time.time() - t0:.0f}s)", flush=True)


async def start():
    uv_config = uvicorn.Config(chainlit_app, host="0.0.0.0", port=8000, log_level="info")
    await uvicorn.Server(uv_config).serve()


print(f"[{time.strftime('%H:%M:%S')}] Starting uvicorn on 0.0.0.0:8000...", flush=True)
asyncio.run(start())
