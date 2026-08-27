import fcntl
import os
from pathlib import Path
from typing import IO


LOCK_NAME = "dell-g-series-controller-brightness.lock"
CONTROLLER_LOCK_NAME = "dell-g-series-controller-device.lock"


def runtime_directory() -> Path:
    configured = os.environ.get("XDG_RUNTIME_DIR")
    if configured:
        return Path(configured)
    return Path(f"/run/user/{os.getuid()}")


def lock_path() -> Path:
    return runtime_directory() / LOCK_NAME


def controller_lock_path() -> Path:
    return runtime_directory() / CONTROLLER_LOCK_NAME


def acquire_controller_lock(path: Path | None = None) -> IO[str]:
    """Serialize complete controller transactions across user processes."""
    path = path or controller_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def acquire_service_lock(path: Path | None = None) -> IO[str]:
    path = path or lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError("another brightness service is already running") from None
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def service_is_running(path: Path | None = None) -> bool:
    path = path or lock_path()
    try:
        handle = path.open("r", encoding="utf-8")
    except OSError:
        return False
    with handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False
