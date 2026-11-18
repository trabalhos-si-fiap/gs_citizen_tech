"""Healthchecks dos containers, sem dependências externas (sem curl na imagem).

Uso:
    python -m app.healthcheck api      # GET http://127.0.0.1:8000/health
    python -m app.healthcheck worker   # heartbeat recente do worker
"""

import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_HEARTBEAT_FILE = "/tmp/worker-heartbeat"


def check_heartbeat(path: Path, max_age_seconds: float) -> bool:
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age <= max_age_seconds


def check_http(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def main(argv: list[str]) -> int:
    target = argv[1] if len(argv) > 1 else "api"
    if target == "api":
        port = os.environ.get("PORT", "8000")
        healthy = check_http(f"http://127.0.0.1:{port}/health")
    elif target == "worker":
        healthy = check_heartbeat(
            Path(os.environ.get("WORKER_HEARTBEAT_FILE", DEFAULT_HEARTBEAT_FILE)),
            float(os.environ.get("WORKER_HEARTBEAT_MAX_AGE_SECONDS", "60")),
        )
    else:
        print(f"Alvo de healthcheck desconhecido: {target}", file=sys.stderr)
        return 2
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
