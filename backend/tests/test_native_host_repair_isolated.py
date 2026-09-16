"""Isolated Windows integration tests for Native Host path repair."""

from __future__ import annotations

import ctypes
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

if os.name == "nt":
    import winreg


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_NAME = "com.ai_job_copilot.service_control"
EXTENSION_ID = "abcdefghijklmnopabcdefghijklmnop"
POWERSHELL = shutil.which("powershell.exe") or "powershell.exe"
REGISTRY_TEST_PARENT = r"Software\AIJobCopilot\Tests"


@dataclass(frozen=True, repr=False)
class IsolatedProject:
    root: Path
    desktop: Path
    manifest: Path
    registry_subkey: str
    registry_ps_path: str
    environment: dict[str, str]


def _windows_temp_directory() -> Path:
    buffer = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetTempPathW(len(buffer), buffer)
    if length == 0 or length >= len(buffer):
        raise ctypes.WinError()
    return Path(buffer.value)


def _remove_registry_tree(subkey: str) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            children = []
            index = 0
            while True:
                try:
                    children.append(winreg.EnumKey(key, index))
                    index += 1
                except OSError:
                    break
        for child in children:
            _remove_registry_tree(f"{subkey}\\{child}")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, subkey)
    except FileNotFoundError:
        return


def _registry_exists(subkey: str) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey):
            return True
    except FileNotFoundError:
        return False


def _read_registry_default(subkey: str) -> str:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as key:
        value, _ = winreg.QueryValueEx(key, "")
    return value


def _write_registry_default(subkey: str, value: Path) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, subkey) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(value.resolve()))


def _registry_children(subkey: str) -> list[str]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as key:
            children = []
            index = 0
            while True:
                try:
                    children.append(winreg.EnumKey(key, index))
                    index += 1
                except OSError:
                    return children
    except FileNotFoundError:
        return []


def _same_path(left: str | Path, right: str | Path) -> bool:
    return Path(left).resolve() == Path(right).resolve()


def _assert_success(completed: subprocess.CompletedProcess[str]) -> None:
    assert completed.returncode == 0


def _run_script(project: IsolatedProject, name: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(POWERSHELL),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(project.root / "scripts" / name),
            *arguments,
        ],
        cwd=project.root,
        env=project.environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _write_manifest(project: IsolatedProject, extension_id: str = EXTENSION_ID) -> None:
    project.manifest.write_text(
        json.dumps(
            {
                "name": HOST_NAME,
                "description": "isolated test host",
                "path": str((project.root / "native_host" / "run_host.bat").resolve()),
                "type": "stdio",
                "allowed_origins": [f"chrome-extension://{extension_id}/"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _read_shortcut(shortcut_path: Path) -> dict[str, str]:
    command = (
        "$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($env:AI_JOB_COPILOT_TEST_SHORTCUT_PATH); "
        "@{ TargetPath = $shortcut.TargetPath; WorkingDirectory = $shortcut.WorkingDirectory } "
        "| ConvertTo-Json -Compress"
    )
    environment = os.environ.copy()
    environment["AI_JOB_COPILOT_TEST_SHORTCUT_PATH"] = str(shortcut_path)
    completed = subprocess.run(
        [str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    return json.loads(completed.stdout)


def _shortcut_matches_project(project: IsolatedProject, shortcut_path: Path) -> bool:
    command = (
        "$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($env:AI_JOB_COPILOT_TEST_SHORTCUT_PATH); "
        "$targetMatches = [System.IO.Path]::GetFullPath($shortcut.TargetPath) -ieq "
        "[System.IO.Path]::GetFullPath($env:AI_JOB_COPILOT_TEST_SHORTCUT_TARGET); "
        "$workingDirectoryMatches = [System.IO.Path]::GetFullPath($shortcut.WorkingDirectory) -ieq "
        "[System.IO.Path]::GetFullPath($env:AI_JOB_COPILOT_TEST_SHORTCUT_WORKING_DIRECTORY); "
        "if ($targetMatches -and $workingDirectoryMatches) { 'MATCH' } else { 'MISMATCH' }"
    )
    environment = os.environ.copy()
    environment["AI_JOB_COPILOT_TEST_SHORTCUT_PATH"] = str(shortcut_path)
    environment["AI_JOB_COPILOT_TEST_SHORTCUT_TARGET"] = str(project.root / "start_demo.bat")
    environment["AI_JOB_COPILOT_TEST_SHORTCUT_WORKING_DIRECTORY"] = str(project.root)
    completed = subprocess.run(
        [str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    return completed.stdout.strip() == "MATCH"


@pytest.fixture
def isolated_project() -> IsolatedProject:
    if os.name != "nt":
        pytest.skip("Registry and Windows shortcut integration tests are Windows-only")

    temp_directory = Path(
        tempfile.mkdtemp(
            prefix="career-matrix-repair-test-",
            dir=_windows_temp_directory(),
        )
    )
    test_key = f"repair_{os.getpid()}_{secrets.token_hex(6)}"
    run_subtree = f"{REGISTRY_TEST_PARENT}\\{test_key}"

    try:
        root = temp_directory / "project"
        scripts = root / "scripts"
        native_host = root / "native_host"
        desktop = temp_directory / "Desktop"
        scripts.mkdir(parents=True)
        native_host.mkdir()
        desktop.mkdir()

        for script_name in (
            "create_desktop_shortcut.ps1",
            "install_native_host.ps1",
            "repair_after_move.ps1",
            "uninstall_native_host.ps1",
        ):
            shutil.copy2(PROJECT_ROOT / "scripts" / script_name, scripts / script_name)
        shutil.copy2(PROJECT_ROOT / "native_host" / "host_manifest.template.json", native_host)
        (native_host / "run_host.bat").write_text("@echo off\r\nexit /b 0\r\n", encoding="ascii")
        (root / "start_demo.bat").write_text("@echo off\r\nexit /b 0\r\n", encoding="ascii")

        registry_subkey = f"{run_subtree}\\{HOST_NAME}"
        environment = os.environ.copy()
        environment["AI_JOB_COPILOT_TEST_REGISTRY_PATH"] = f"HKCU:\\{registry_subkey}"
        environment["AI_JOB_COPILOT_TEST_DESKTOP_PATH"] = str(desktop)
        project = IsolatedProject(
            root=root,
            desktop=desktop,
            manifest=native_host / "host_manifest.json",
            registry_subkey=registry_subkey,
            registry_ps_path=f"HKCU:\\{registry_subkey}",
            environment=environment,
        )

        yield project
    finally:
        _remove_registry_tree(run_subtree)
        shutil.rmtree(temp_directory, ignore_errors=False)
        assert not _registry_exists(run_subtree)
        assert not temp_directory.exists()


def _assert_shortcut_targets_project(project: IsolatedProject) -> None:
    shortcuts = list(project.desktop.glob("*.lnk"))
    assert [shortcut.name for shortcut in shortcuts] == ["CareerMatrix.lnk"]
    assert _shortcut_matches_project(project, shortcuts[0])


def test_case_a_no_registration_installs_and_repairs(isolated_project: IsolatedProject) -> None:
    project = isolated_project
    assert not _registry_exists(project.registry_subkey)

    installed = _run_script(project, "install_native_host.ps1", EXTENSION_ID)
    _assert_success(installed)
    assert _same_path(_read_registry_default(project.registry_subkey), project.manifest)

    repaired = _run_script(project, "repair_after_move.ps1")
    _assert_success(repaired)
    assert _same_path(_read_registry_default(project.registry_subkey), project.manifest)
    _assert_shortcut_targets_project(project)


def test_case_b_stale_path_is_replaced(isolated_project: IsolatedProject) -> None:
    project = isolated_project
    stale_manifest = project.root.parent / "old-project" / "native_host" / "host_manifest.json"
    assert not stale_manifest.exists()
    _write_registry_default(project.registry_subkey, stale_manifest)
    _write_manifest(project)

    repaired = _run_script(project, "repair_after_move.ps1")
    _assert_success(repaired)
    assert _same_path(_read_registry_default(project.registry_subkey), project.manifest)
    assert not _same_path(stale_manifest, _read_registry_default(project.registry_subkey))
    assert _registry_children(project.registry_subkey) == []
    assert _registry_children(project.registry_subkey.rsplit("\\", 1)[0]) == [HOST_NAME]


def test_case_c_other_live_project_is_preserved(isolated_project: IsolatedProject) -> None:
    project = isolated_project
    other_manifest = project.root.parent / "other-project" / "native_host" / "host_manifest.json"
    other_manifest.parent.mkdir(parents=True)
    other_manifest.write_text("{}", encoding="utf-8")
    _write_registry_default(project.registry_subkey, other_manifest)
    _write_manifest(project)

    repaired = _run_script(project, "repair_after_move.ps1")
    assert repaired.returncode != 0
    assert "another active project directory" in (repaired.stdout + repaired.stderr)
    assert _same_path(_read_registry_default(project.registry_subkey), other_manifest)
    assert other_manifest.read_text(encoding="utf-8") == "{}"
    assert other_manifest.parent.parent.exists()
    assert _registry_children(project.registry_subkey) == []

    uninstalled = _run_script(project, "uninstall_native_host.ps1")
    assert uninstalled.returncode != 0
    assert "another active project directory" in (uninstalled.stdout + uninstalled.stderr)
    assert _same_path(_read_registry_default(project.registry_subkey), other_manifest)
    assert other_manifest.read_text(encoding="utf-8") == "{}"


def test_case_d_valid_manifest_reuses_extension_id(isolated_project: IsolatedProject) -> None:
    project = isolated_project
    _write_manifest(project)

    installed = _run_script(project, "install_native_host.ps1")
    _assert_success(installed)
    manifest = json.loads(project.manifest.read_text(encoding="utf-8"))
    assert manifest["allowed_origins"] == [f"chrome-extension://{EXTENSION_ID}/"]
    assert _same_path(_read_registry_default(project.registry_subkey), project.manifest)


def test_case_e_missing_manifest_leaves_no_partial_host(isolated_project: IsolatedProject) -> None:
    project = isolated_project
    assert not project.manifest.exists()

    install = _run_script(project, "install_native_host.ps1")
    assert install.returncode != 0
    assert "Extension ID is required" in (install.stdout + install.stderr)
    assert not project.manifest.exists()
    assert not _registry_exists(project.registry_subkey)

    repair = _run_script(project, "repair_after_move.ps1")
    _assert_success(repair)
    assert not project.manifest.exists()
    assert not _registry_exists(project.registry_subkey)
    _assert_shortcut_targets_project(project)


def test_case_f_repair_is_idempotent(isolated_project: IsolatedProject) -> None:
    project = isolated_project
    _write_manifest(project)

    first = _run_script(project, "repair_after_move.ps1")
    _assert_success(first)
    first_registry = _read_registry_default(project.registry_subkey)
    first_manifest = project.manifest.read_bytes()
    first_shortcut = _read_shortcut(project.desktop / "CareerMatrix.lnk")

    second = _run_script(project, "repair_after_move.ps1")
    _assert_success(second)
    assert _read_registry_default(project.registry_subkey) == first_registry
    assert project.manifest.read_bytes() == first_manifest
    assert _read_shortcut(project.desktop / "CareerMatrix.lnk") == first_shortcut
    _assert_shortcut_targets_project(project)


def test_shortcut_create_update_and_idempotency(isolated_project: IsolatedProject) -> None:
    project = isolated_project
    shortcut_path = project.desktop / "CareerMatrix.lnk"

    created = _run_script(project, "create_desktop_shortcut.ps1")
    _assert_success(created)
    _assert_shortcut_targets_project(project)

    old_target = project.root.parent / "old-project" / "start_demo.bat"
    command = (
        "$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($env:AI_JOB_COPILOT_TEST_SHORTCUT_PATH); "
        "$shortcut.TargetPath = $env:AI_JOB_COPILOT_TEST_SHORTCUT_TARGET; $shortcut.Save()"
    )
    environment = os.environ.copy()
    environment["AI_JOB_COPILOT_TEST_SHORTCUT_PATH"] = str(shortcut_path)
    environment["AI_JOB_COPILOT_TEST_SHORTCUT_TARGET"] = str(old_target)
    subprocess.run(
        [str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )

    updated = _run_script(project, "create_desktop_shortcut.ps1")
    _assert_success(updated)
    _assert_shortcut_targets_project(project)

    repeated = _run_script(project, "create_desktop_shortcut.ps1")
    _assert_success(repeated)
    _assert_shortcut_targets_project(project)


def test_test_overrides_reject_unsafe_paths(isolated_project: IsolatedProject) -> None:
    project = isolated_project
    unsafe_registry_environment = project.environment.copy()
    unsafe_registry_environment["AI_JOB_COPILOT_TEST_REGISTRY_PATH"] = (
        f"HKCU:\\Software\\Microsoft\\Edge\\NativeMessagingHosts\\{HOST_NAME}"
    )
    unsafe_registry_project = IsolatedProject(
        root=project.root,
        desktop=project.desktop,
        manifest=project.manifest,
        registry_subkey=project.registry_subkey,
        registry_ps_path=project.registry_ps_path,
        environment=unsafe_registry_environment,
    )
    registry_attempt = _run_script(unsafe_registry_project, "install_native_host.ps1", EXTENSION_ID)
    assert registry_attempt.returncode != 0
    assert "test Registry path must be inside" in (registry_attempt.stdout + registry_attempt.stderr)

    unsafe_desktop_environment = project.environment.copy()
    unsafe_desktop_environment["AI_JOB_COPILOT_TEST_DESKTOP_PATH"] = str(PROJECT_ROOT)
    unsafe_desktop_project = IsolatedProject(
        root=project.root,
        desktop=project.desktop,
        manifest=project.manifest,
        registry_subkey=project.registry_subkey,
        registry_ps_path=project.registry_ps_path,
        environment=unsafe_desktop_environment,
    )
    desktop_attempt = _run_script(unsafe_desktop_project, "create_desktop_shortcut.ps1")
    assert desktop_attempt.returncode != 0
    assert "test Desktop path must be inside" in (desktop_attempt.stdout + desktop_attempt.stderr)
