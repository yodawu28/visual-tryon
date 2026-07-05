from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.local_visual_engine.leffa_engine import LeffaVisualEngine


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local visual engine service.")
    parser.add_argument(
        "--host",
        default=os.environ.get("LOCAL_VISUAL_ENGINE_SERVICE_HOST", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LOCAL_VISUAL_ENGINE_SERVICE_PORT", "8091")),
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO").upper(),
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser.parse_args()


def build_engine_from_env() -> LeffaVisualEngine:
    from src.modules.local_visual_engine.leffa_engine import LeffaVisualEngine

    engine = os.environ.get("LOCAL_VISUAL_ENGINE_ENGINE", "leffa").lower()
    if engine != "leffa":
        raise ValueError("Local visual engine service supports only leffa")

    return LeffaVisualEngine(
        leffa_root=Path(os.environ.get("LOCAL_LEFFA_ROOT", "models/external/Leffa")),
        repo_url=os.environ.get(
            "LOCAL_LEFFA_REPO_URL",
            "https://github.com/franciszzj/Leffa.git",
        ),
        no_clone=_env_flag("LOCAL_LEFFA_NO_CLONE", True),
        model_repo_id=os.environ.get("LOCAL_LEFFA_MODEL_REPO_ID", "franciszzj/Leffa"),
        checkpoint_dir=Path(
            os.environ.get(
                "LOCAL_LEFFA_CHECKPOINT_DIR",
                "models/external/Leffa/ckpts",
            )
        ),
        size=os.environ.get("LOCAL_LEFFA_SIZE", "768x1024"),
        device=os.environ.get("LOCAL_LEFFA_DEVICE", "cuda"),
        dtype=os.environ.get("LOCAL_LEFFA_DTYPE", "float16"),
        vt_model_type=os.environ.get("LOCAL_LEFFA_VT_MODEL_TYPE", "viton_hd"),
        allow_tf32=True,
    )


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    from src.modules.local_visual_engine.service import LocalVisualEngineHTTPServer

    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    engine = build_engine_from_env()
    server = LocalVisualEngineHTTPServer(host=args.host, port=args.port, engine=engine)
    server.load_engine()
    host, port = server.server_address
    logger.info("Local visual engine service ready at http://%s:%s", host, port)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
