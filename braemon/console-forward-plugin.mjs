/**
 * Vite plugin — forwards browser console output to Vite dev server terminal.
 * Records all console.log/warn/error + uncaught exceptions.
 */

const VIRTUAL_ID = "virtual:console-forward";
const RESOLVED_ID = "\0" + VIRTUAL_ID;

function consoleForwardPlugin() {
	let viteConfig;

	return {
		name: "braemon-console-forward",
		apply: "serve",
		configResolved(config) {
			viteConfig = config;
		},

		resolveId(id) {
			if (id === VIRTUAL_ID) return RESOLVED_ID;
		},

		load(id) {
			if (id !== RESOLVED_ID) return;
			// Injected script that runs in the browser
			return `
(function() {
  const BATCH_INTERVAL = 200;
  const MAX_BATCH = 20;
  let queue = [];
  let timer = null;

  function flush() {
    if (!queue.length) return;
    const payload = queue.splice(0);
    try {
      fetch('/__console_forward', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      });
    } catch {}
  }

  function scheduleFlush() {
    if (timer) return;
    timer = setTimeout(() => { timer = null; flush(); }, BATCH_INTERVAL);
  }

  function push(level, args) {
    queue.push({ level, args: Array.from(args).map(a => {
      try { return typeof a === 'object' ? JSON.stringify(a) : String(a); }
      catch { return String(a); }
    }), time: new Date().toISOString() });
    if (queue.length >= MAX_BATCH) { clearTimeout(timer); timer = null; flush(); }
    else scheduleFlush();
  }

  // Intercept console methods
  ['log','warn','error','info','debug'].forEach(level => {
    const orig = console[level];
    console[level] = function(...args) {
      push(level, args);
      orig.apply(console, args);
    };
  });

  // Intercept uncaught errors
  window.addEventListener('error', e => {
    push('error', [e.message, 'at', e.filename + ':' + e.lineno + ':' + e.colno]);
  });
  window.addEventListener('unhandledrejection', e => {
    push('error', ['Unhandled rejection:', e.reason]);
  });
})();
`;
		},

		transformIndexHtml: {
			order: "pre",
			handler() {
				return [
					{
						tag: "script",
						attrs: { type: "module" },
						children: `import '${VIRTUAL_ID}'`,
					},
				];
			},
		},

		configureServer(server) {
			server.middlewares.use("/__console_forward", (req, res, next) => {
				if (req.method !== "POST") return next();
				let body = "";
				req.on("data", (chunk) => {
					body += chunk;
				});
				req.on("end", () => {
					try {
						const entries = JSON.parse(body);
						for (const e of entries) {
							const label =
								{
									log: "\x1b[37m", // white
									warn: "\x1b[33m", // yellow
									error: "\x1b[31m", // red
									info: "\x1b[36m", // cyan
									debug: "\x1b[35m", // magenta
								}[e.level] || "\x1b[37m";
							const reset = "\x1b[0m";
							console.log(
								`${label}[browser ${e.level}]${reset}`,
								e.args.join(" "),
							);
						}
					} catch {}
					res.statusCode = 204;
					res.end();
				});
			});
		},
	};
}

export default consoleForwardPlugin;
