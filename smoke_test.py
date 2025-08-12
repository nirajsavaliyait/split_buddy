import sys
import os
from pathlib import Path
import importlib.util
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent

services: List[Tuple[str, str]] = [
    (ROOT / "UserAuthentication", "UserAuthentication"),
    (ROOT / "UserAuthorisation", "UserAuthorisation"),
    (ROOT / "UserGroupManagement", "UserGroupManagement"),
    (ROOT / "ExpenseManagement", "ExpenseManagement"),
]


def load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def check_service(service_dir: Path, name: str) -> bool:
    cwd = Path.cwd()
    unique_name = f"main_{name}"
    try:
        # Ensure relative paths (e.g., StaticFiles(directory="app/form")) resolve correctly
        os.chdir(service_dir)
        # Ensure 'app' package inside the service is importable
        sys.path.insert(0, str(service_dir))
        # Remove any previously loaded 'app' modules to prevent cross-service contamination
        to_delete = [k for k in list(sys.modules.keys()) if k == 'app' or k.startswith('app.')]
        for k in to_delete:
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
        from starlette.testclient import TestClient
        client = TestClient(app)
        r = client.get("/openapi.json")
        if r.status_code == 200:
            print(f"{name}: OK")
            return True
        else:
            print(f"{name}: FAIL ({r.status_code})")
            return False
    except Exception as e:
        print(f"{name}: EXCEPTION - {e}")
        return False
    finally:
        # Cleanup
        os.chdir(cwd)
        if str(service_dir) in sys.path:
            try:
                sys.path.remove(str(service_dir))
            except ValueError:
                pass
        sys.modules.pop(unique_name, None)
        # Purge 'app' modules loaded for this service
        to_delete = [k for k in list(sys.modules.keys()) if k == 'app' or k.startswith('app.')]
        for k in to_delete:
            sys.modules.pop(k, None)


if __name__ == "__main__":
    ok = True
    for path, name in services:
        ok = check_service(Path(path), name) and ok
    if not ok:
        raise SystemExit(1)
