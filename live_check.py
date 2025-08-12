import sys
import os
import time
import threading
from pathlib import Path
from typing import List, Tuple
import importlib.util
import requests
import uvicorn

ROOT = Path(__file__).resolve().parent

services: List[Tuple[Path, str, int]] = [
    (ROOT / "UserAuthentication", "UserAuthentication", 8001),
    (ROOT / "UserAuthorisation", "UserAuthorisation", 8002),
    (ROOT / "UserGroupManagement", "UserGroupManagement", 8003),
    (ROOT / "ExpenseManagement", "ExpenseManagement", 8004),
]


def load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def run_service_once(service_dir: Path, name: str, port: int) -> bool:
    cwd = Path.cwd()
    unique_name = f"main_live_{name}"
    try:
        os.chdir(service_dir)
        sys.path.insert(0, str(service_dir))
        # Clean previous 'app' modules
        for k in [k for k in list(sys.modules.keys()) if k == 'app' or k.startswith('app.')]:
            sys.modules.pop(k, None)
        main_py = service_dir / "main.py"
        if not main_py.exists():
            print(f"{name}: FAIL (no main.py)")
            return False
        m = load_module_from_path(unique_name, main_py)
        app = getattr(m, "app", None)
        if app is None:
            print(f"{name}: FAIL (no app)")
            return False

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        t = threading.Thread(target=server.run, daemon=True)
        t.start()

        # Poll until up or timeout
        url = f"http://127.0.0.1:{port}/openapi.json"
        deadline = time.time() + 12
        ok = False
        while time.time() < deadline:
            try:
                r = requests.get(url, timeout=1.5)
                if r.status_code == 200:
                    ok = True
                    break
            except Exception:
                pass
            time.sleep(0.3)
        # Print result
        if ok:
            print(f"{name}: LIVE OK")
        else:
            print(f"{name}: LIVE FAIL (no response)")

        # Stop server
        server.should_exit = True
        t.join(timeout=5)
        return ok
    except Exception as e:
        print(f"{name}: EXCEPTION - {e}")
        return False
    finally:
        os.chdir(cwd)
        if str(service_dir) in sys.path:
            try:
                sys.path.remove(str(service_dir))
            except ValueError:
                pass
        sys.modules.pop(unique_name, None)
        # Purge 'app' modules
        for k in [k for k in list(sys.modules.keys()) if k == 'app' or k.startswith('app.')]:
            sys.modules.pop(k, None)


if __name__ == "__main__":
    overall = True
    for path, name, port in services:
        overall = run_service_once(Path(path), name, port) and overall
    if not overall:
        raise SystemExit(1)
