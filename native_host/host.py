"""Short-lived Microsoft Edge Native Messaging host for backend control."""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
import re
import struct
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = PROJECT_ROOT / "scripts" / "start_backend.ps1"
STOP_SCRIPT = PROJECT_ROOT / "scripts" / "stop_backend.ps1"
ENV_FILE = PROJECT_ROOT / ".env"
HEALTH_URL = "http://127.0.0.1:8000/health"
BACKEND_PORT = 8000
MAX_MESSAGE_BYTES = 64 * 1024
VALID_STATES = {"stopped", "starting", "running", "stopping", "error"}


class NativeMessageError(ValueError):
    """A safe protocol error that may be returned to the extension."""


def _read_exact(stream: BinaryIO, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = stream.read(length - len(chunks))
        if not chunk:
            raise NativeMessageError("Native Messaging 消息不完整")
        chunks.extend(chunk)
    return bytes(chunks)


def read_message(stream: BinaryIO) -> dict[str, object]:
    try:
        header = _read_exact(stream, 4)
    except NativeMessageError as exc:
        raise NativeMessageError("Native Messaging 消息长度无效") from exc
    length = struct.unpack("<I", header)[0]
    if length == 0 or length > MAX_MESSAGE_BYTES:
        raise NativeMessageError("Native Messaging 消息长度无效")
    try:
        value = json.loads(_read_exact(stream, length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeMessageError("Native Messaging JSON 无效") from exc
    if not isinstance(value, dict):
        raise NativeMessageError("Native Messaging JSON 必须是对象")
    return value


def write_message(stream: BinaryIO, response: dict[str, object]) -> None:
    state = response.get("state")
    if state not in VALID_STATES:
        raise ValueError("invalid response state")
    payload = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream.write(struct.pack("<I", len(payload)))
    stream.write(payload)
    stream.flush()


def is_backend_healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1.5) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read(4096).decode("utf-8"))
            return isinstance(payload, dict) and payload.get("status") == "ok"
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _normalized_project_path(value: object) -> str:
    """Normalize a Windows project path across case, slash, and relative forms."""
    try:
        resolved = str(Path(str(value)).resolve())
    except (OSError, RuntimeError, ValueError):
        return ""
    return ntpath.normcase(ntpath.normpath(resolved)).rstrip("\\/")


def _state_file_path() -> Path:
    normalized = str(PROJECT_ROOT.resolve()).rstrip("\\").lower().encode("utf-8")
    project_id = hashlib.sha256(normalized).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / "AIJobCopilot" / f"backend-{project_id}.json"


def _windows_process_pair(
    listener_pid: int,
    host_pid: int,
) -> tuple[int, str, str, str] | None:
    """Query the expected Uvicorn child and PowerShell parent in one operation."""
    if os.name != "nt" or listener_pid <= 0 or host_pid <= 0:
        return None
    command = (
        "$listener = Get-CimInstance Win32_Process "
        f"-Filter 'ProcessId = {listener_pid}' -ErrorAction SilentlyContinue; "
        "$hostProcess = Get-CimInstance Win32_Process "
        f"-Filter 'ProcessId = {host_pid}' -ErrorAction SilentlyContinue; "
        "if ($null -ne $listener -and $null -ne $hostProcess) { "
        "[pscustomobject]@{ ListenerParentProcessId = [int]$listener.ParentProcessId; "
        "ListenerName = [string]$listener.Name; "
        "ListenerCommandLine = [string]$listener.CommandLine; "
        "HostName = [string]$hostProcess.Name } "
        "| ConvertTo-Json -Compress }"
    )
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return None
        value = json.loads(completed.stdout)
        return (
            int(value.get("ListenerParentProcessId") or 0),
            str(value.get("ListenerName") or ""),
            str(value.get("ListenerCommandLine") or ""),
            str(value.get("HostName") or ""),
        )
    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ):
        return None


def _pid_owns_backend_port(pid: int) -> bool:
    """Confirm that the recorded process is the listener on the fixed backend port."""
    if os.name != "nt" or pid <= 0:
        return False
    try:
        completed = subprocess.run(
            ["netstat.exe", "-ano", "-p", "tcp"],
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if completed.returncode != 0:
        return False
    pattern = re.compile(
        rf"^\s*TCP\s+\S+:{BACKEND_PORT}\s+\S+\s+LISTENING\s+{pid}\s*$",
        re.IGNORECASE,
    )
    return any(pattern.match(line) for line in completed.stdout.splitlines())


def _process_matches_backend(listener_pid: int, host_pid: int) -> bool:
    """Validate the expected PowerShell parent and Python/Uvicorn child."""
    process_pair = _windows_process_pair(listener_pid, host_pid)
    if process_pair is None:
        return False
    parent_pid, listener_name, command_line, host_name = process_pair
    normalized_command = command_line.lower().replace("\\", "/")
    return (
        parent_pid == host_pid
        and "python" in listener_name.lower()
        and "powershell" in host_name.lower()
        and "uvicorn" in normalized_command
        and "backend.app.main:app" in normalized_command
    )


def _backend_state_matches_project() -> bool:
    state_path = _state_file_path()
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
        listener_pid = int(state.get("ListenerProcessId") or 0)
        host_pid = int(state.get("HostProcessId") or 0)
        if _normalized_project_path(state.get("ProjectRoot")) != _normalized_project_path(
            PROJECT_ROOT
        ):
            return False
        if listener_pid <= 0 or host_pid <= 0:
            return False
        return _pid_owns_backend_port(listener_pid) and _process_matches_backend(
            listener_pid,
            host_pid,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def is_current_backend_healthy() -> bool:
    return _backend_state_matches_project() and is_backend_healthy()


def _run_fixed_script(
    script: Path,
    timeout: float,
    *,
    hidden_backend_window: bool = False,
) -> bool:
    if not script.is_file() or script.parent.resolve() != (PROJECT_ROOT / "scripts").resolve():
        return False
    arguments = [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
    ]
    if hidden_backend_window:
        arguments.append("-Hidden")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        completed = subprocess.run(
            arguments,
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
            shell=False,
            creationflags=creationflags,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def status_action() -> dict[str, object]:
    running = is_current_backend_healthy()
    return {
        "ok": True,
        "state": "running" if running else "stopped",
        "message": "本地服务正在运行" if running else "本地服务已停止",
    }


def start_action() -> dict[str, object]:
    if is_current_backend_healthy():
        return {"ok": True, "state": "running", "message": "本地服务正在运行"}
    if not _run_fixed_script(START_SCRIPT, 15.0, hidden_backend_window=True):
        return {"ok": False, "state": "error", "message": "本地服务启动失败，请检查后端日志"}
    if is_current_backend_healthy():
        return {"ok": True, "state": "running", "message": "本地服务已启动"}
    return {"ok": True, "state": "starting", "message": "本地服务正在启动"}


def stop_action() -> dict[str, object]:
    if not is_backend_healthy():
        return {"ok": True, "state": "stopped", "message": "本地服务已停止"}
    if not _run_fixed_script(STOP_SCRIPT, 10.0):
        return {"ok": False, "state": "error", "message": "本地服务停止失败，请手动检查"}
    if is_current_backend_healthy():
        return {"ok": True, "state": "stopping", "message": "本地服务正在停止"}
    return {"ok": True, "state": "stopped", "message": "本地服务已停止"}


def read_demo_token(env_file: Path = ENV_FILE) -> str | None:
    """Return the first DEMO_AUTH_TOKENS key, read the same way as the backend."""
    raw = os.environ.get("DEMO_AUTH_TOKENS")
    if raw is None:
        try:
            lines = env_file.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            return None
        for line in lines:
            name, separator, value = line.partition("=")
            if separator and name.strip() == "DEMO_AUTH_TOKENS":
                raw = value.strip()
        if raw is None:
            return None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        raw = raw[1:-1]
    try:
        tokens = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(tokens, dict):
        return None
    for token in tokens:
        if isinstance(token, str) and token and not any(c.isspace() for c in token):
            return token
    return None


def demo_token_action() -> dict[str, object]:
    # Only the extension listed in the host manifest can call this host.
    token = read_demo_token()
    if token is None:
        return {"ok": False, "state": "error", "message": "未在 .env 中找到 DEMO_AUTH_TOKENS"}
    return {"ok": True, "state": "running", "token": token}


ACTIONS: dict[str, Callable[[], dict[str, object]]] = {
    "status": status_action,
    "start": start_action,
    "stop": stop_action,
    "demo_token": demo_token_action,
}


def handle_message(message: dict[str, object]) -> dict[str, object]:
    action = message.get("action")
    if not isinstance(action, str) or action not in ACTIONS:
        return {"ok": False, "state": "error", "message": "不支持的本地服务操作"}
    return ACTIONS[action]()


def _set_binary_stdio() -> None:
    if os.name == "nt":
        import msvcrt  # pylint: disable=import-outside-toplevel

        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)


def main() -> int:
    _set_binary_stdio()
    try:
        response = handle_message(read_message(sys.stdin.buffer))
    except NativeMessageError as exc:
        response = {"ok": False, "state": "error", "message": str(exc)}
    except Exception:  # noqa: BLE001 - last-resort reply; never expose a traceback.
        response = {"ok": False, "state": "error", "message": "本地连接组件发生安全错误"}
    write_message(sys.stdout.buffer, response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
