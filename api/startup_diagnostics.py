import importlib
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from src.shared.paths import MFA_BASE_DIR, MFA_RUNTIME_DIR, REFERENCE_DATA_DIR, USER_UPLOADS_DIR
from src.shared.services import ASR_HEALTH_URL, PHONEME_HEALTH_URL


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_project_path(project_root: Path, configured_path: Path) -> Path:
    try:
        rel_path = configured_path.relative_to(DEFAULT_PROJECT_ROOT)
        return project_root / rel_path
    except ValueError:
        return configured_path


def check_python_modules(module_names):
    results = []
    for module_name in module_names:
        entry = {"name": module_name, "ok": True, "error": None}
        try:
            importlib.import_module(module_name)
        except Exception as exception:  # pragma: no cover - defensive path
            entry["ok"] = False
            entry["error"] = str(exception)
        results.append(entry)
    return results


def check_service_health(name, url, timeout=1.5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="ignore")
            return {"name": name, "ok": True, "status": response.status, "body": body[:200]}
    except urllib.error.URLError as exception:
        return {"name": name, "ok": False, "error": str(exception)}
    except Exception as exception:  # pragma: no cover - defensive path
        return {"name": name, "ok": False, "error": str(exception)}


def check_directories(paths):
    results = []
    for path in paths:
        candidate = Path(path)
        results.append(
            {
                "path": str(candidate),
                "exists": candidate.exists(),
                "is_dir": candidate.is_dir(),
            }
        )
    return results


def check_docker_cli():
    try:
        completed = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "version": completed.stdout.strip(),
            "error": completed.stderr.strip() if completed.returncode != 0 else None,
        }
    except Exception as exception:
        return {"ok": False, "version": "", "error": str(exception)}


def run_startup_diagnostics(project_root):
    root = Path(project_root)

    module_checks = check_python_modules(
        [
            "api.app",
            "api.validator",
            "pte_core.asr.voice2text",
            "pte_core.asr.phoneme_recognition",
        ]
    )
    directory_checks = check_directories(
        [
            _resolve_project_path(root, USER_UPLOADS_DIR),
            _resolve_project_path(root, REFERENCE_DATA_DIR),
            _resolve_project_path(root, MFA_BASE_DIR),
            _resolve_project_path(root, MFA_RUNTIME_DIR),
        ]
    )
    service_checks = [
        check_service_health("asr_grammar", ASR_HEALTH_URL),
        check_service_health("phoneme", PHONEME_HEALTH_URL),
    ]
    docker_check = check_docker_cli()

    hard_failure = any(not item["ok"] for item in module_checks) or any(
        not entry["exists"] for entry in directory_checks
    )

    return {
        "ok": not hard_failure,
        "modules": module_checks,
        "directories": directory_checks,
        "services": service_checks,
        "docker": docker_check,
    }


def main():
    project_root = Path(__file__).resolve().parent.parent
    report = run_startup_diagnostics(project_root)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
