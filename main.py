"""Anki Manager entry point.

Directs execution to the web server (FastAPI + React Dashboard).
CLI has been retired in favor of the web dashboard.
"""
from __future__ import annotations

import uvicorn


def main() -> None:
    print("Starting Anki Manager Web Server on http://localhost:8001...")
    uvicorn.run("server:app", host="127.0.0.1", port=8001, reload=True)


if __name__ == "__main__":
    main()
