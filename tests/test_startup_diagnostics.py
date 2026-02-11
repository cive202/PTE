from pathlib import Path

import api.startup_diagnostics as diagnostics_module


def test_check_python_modules_handles_success_and_failure():
    results = diagnostics_module.check_python_modules(["json", "this_module_should_not_exist_123"])
    by_name = {entry["name"]: entry for entry in results}

    assert by_name["json"]["ok"] is True
    assert by_name["this_module_should_not_exist_123"]["ok"] is False
    assert by_name["this_module_should_not_exist_123"]["error"]


def test_check_directories_reports_flags(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()

    results = diagnostics_module.check_directories([existing, tmp_path / "missing"])
    by_path = {entry["path"]: entry for entry in results}

    assert by_path[str(existing)]["exists"] is True
    assert by_path[str(existing)]["is_dir"] is True
    assert by_path[str(tmp_path / "missing")]["exists"] is False


def test_run_startup_diagnostics_contract(tmp_path, monkeypatch):
    project_root = tmp_path
    (project_root / "data" / "user_uploads").mkdir(parents=True)
    (project_root / "data" / "reference").mkdir(parents=True)
    (project_root / "data" / "processed" / "mfa_runs").mkdir(parents=True)
    (project_root / "data" / "models" / "mfa").mkdir(parents=True)

    monkeypatch.setattr(
        diagnostics_module,
        "check_python_modules",
        lambda _modules: [{"name": "mock", "ok": True, "error": None}],
    )
    monkeypatch.setattr(
        diagnostics_module,
        "check_service_health",
        lambda name, _url, timeout=1.5: {"name": name, "ok": True, "status": 200, "body": "ok"},
    )
    monkeypatch.setattr(
        diagnostics_module,
        "check_docker_cli",
        lambda: {"ok": True, "version": "docker 1.0", "error": None},
    )

    report = diagnostics_module.run_startup_diagnostics(Path(project_root))
    assert report["ok"] is True
    assert set(report.keys()) == {"ok", "modules", "directories", "services", "docker"}
    assert isinstance(report["directories"], list)
    assert len(report["services"]) == 2
