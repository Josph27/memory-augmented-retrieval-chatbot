# Breamon — Custom React Frontend

Breamon is the React 18 SPA frontend for the multi-agent typed-memory RAG chatbot.
It wraps `@chainlit/react-client` WebSocket hooks with a custom dark-themed UI
("Stitch" design system) and multi-page workspace (chats, documents, memories,
diagnostics, retrieval logs).

## Quick start

```bash
cd braemon
npm install
npm run dev
```

The dev server runs on port 5173 and proxies `/api/*` and `/ws` to the Python
Chainlit backend on `localhost:8000`.

The Python backend must be running first (`uv run python startup.py -w`).

## Architecture

- **7 routes**: Home, Chat, Chats, Documents, Memories, Diagnostics, RetrievalLogs
- **2 data channels**: REST API (20 functions via Vite proxy) + Chainlit WebSocket
- **Design system**: "Stitch" — 50 M3 colors, 5 semantic aliases, Inter typography, Tailwind v4
- **No TypeScript** — plain JSX with Oxlint

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Production build → `dist/` |
| `npm run lint` | Oxlint static analysis |
| `npm run test:e2e` | Puppeteer E2E chat tests |
| `npm run preview` | Preview production build |

## Key files

| File | Role |
|---|---|
| `src/main.jsx` | Bootstrap: Recoil, ChainlitAPI, AuthWrapper, ModelLoadingScreen |
| `src/App.jsx` | Route definitions (7 routes) |
| `src/api.js` | REST client — 20 functions |
| `src/index.css` | Stitch design tokens + custom utilities |
| `src/components/ChainlitChat.jsx` | Core chat: WebSocket, messages, trace display |
| `src/components/ModelLoadingScreen.jsx` | Startup gate: polls backend until models ready |

See `.doc.md` for comprehensive documentation.
