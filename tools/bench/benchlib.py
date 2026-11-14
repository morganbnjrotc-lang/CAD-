# SPDX-License-Identifier: LGPL-2.1-or-later
"""Helpers shared by the benchmarks in tools/bench and the probes they run inside FreeCAD.

Standard library only: the probes import this module inside FreeCAD, and tools/repo_tests import
the benchmarks on CI machines without a FreeCAD build.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


# A brand-new user.cfg except for one setting: the "Invalid OpenGL Version" warning counts as
# dismissed ("don't show again"). Release builds show that modal warning at startup when only
# OpenGL 1.x is available (src/Gui/StartupProcess.cpp, checkOpenGL), as on GitHub's GPU-less
# Windows runners. It never shows on a machine with a real GPU, so this changes nothing there.
_USER_CFG = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<FCParameters>
  <FCParamGroup Name="Root">
    <FCParamGroup Name="BaseApp">
      <FCParamGroup Name="CheckMessages">
        <FCBool Name="FreeCAD_-_Invalid_OpenGL_Version" Value="1"/>
      </FCParamGroup>
    </FCParamGroup>
  </FCParamGroup>
</FCParameters>
"""


def make_profile(root: Path) -> dict:
    """Creates a throwaway FreeCAD profile under `root`; returns the environment variables for it.

    Isolates home, data AND temp: FreeCAD keeps lock files in its temp cache, and sharing it with
    another running FreeCAD (e.g. a test run) can make that process wait forever. FreeCAD silently
    ignores these variables unless the folders already exist.
    """
    for sub in ("home", "data", "temp"):
        (root / sub).mkdir()
    (root / "home" / "user.cfg").write_text(_USER_CFG, encoding="utf-8")
    return {
        "FREECAD_USER_HOME": str(root / "home"),
        "FREECAD_USER_DATA": str(root / "data"),
        "FREECAD_USER_TEMP": str(root / "temp"),
    }


def run_probe(exe: Path, probe: Path, env: dict, timeout: float) -> dict:
    """Runs `exe probe` in a fresh throwaway FreeCAD profile and returns the JSON the probe wrote.

    The probe writes its result to the file named in STUDIO_BENCH_OUT. The returned dict also
    has "launched": the wall-clock time just before the process started.
    """
    with tempfile.TemporaryDirectory(prefix="studio-bench-") as tmp:
        tmp = Path(tmp)
        out = tmp / "result.json"
        full_env = dict(os.environ)
        full_env.update(make_profile(tmp), STUDIO_BENCH_OUT=str(out), **env)
        log = tmp / "freecad.log"
        launched = time.time()
        try:
            proc = subprocess.run(
                [str(exe), "--log-file", str(log), str(probe)],
                env=full_env,
                timeout=timeout,
                capture_output=True,
                text=True,
            )
            output = proc.stdout + proc.stderr
            status = f"exit code {proc.returncode}"
        except subprocess.TimeoutExpired as exc:
            output = _text(exc.stdout) + _text(exc.stderr)
            status = f"killed after {timeout} s"
        finally:
            # FreeCAD can relaunch itself as a detached process (e.g. one-time first-run setup);
            # that copy outlives the one we started, so close anything still running our probe.
            kill_leftover(probe.name)
        if not out.exists():
            tail = log.read_text(encoding="utf-8", errors="replace")[-3000:] if log.exists() else ""
            raise RuntimeError(
                f"probe did not report ({status})\n"
                f"--- stdout/stderr ---\n{output[-2000:]}\n"
                f"--- FreeCAD log ---\n{tail}"
            )
        data = json.loads(out.read_text(encoding="utf-8"))
        data["launched"] = launched
        return data


def _text(stream) -> str:
    if stream is None:
        return ""
    return stream.decode(errors="replace") if isinstance(stream, bytes) else stream


def kill_leftover(probe_name: str) -> None:
    """Stops any FreeCAD.exe still running the given probe file."""
    if sys.platform != "win32":
        return
    subprocess.run(
        [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='FreeCAD.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*{probe_name}*' }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }",
        ],
        check=False,
        capture_output=True,
    )


def process_memory() -> dict:
    """Working set and private bytes of the current process in MB (Windows; {} elsewhere)."""
    if sys.platform != "win32":
        return {}
    import ctypes
    import ctypes.wintypes as wt

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wt.DWORD),
            ("PageFaultCount", wt.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = wt.HANDLE
    get_info = kernel32.K32GetProcessMemoryInfo
    get_info.argtypes = [wt.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wt.DWORD]
    get_info.restype = wt.BOOL
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not get_info(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    return {
        "working_set_mb": counters.WorkingSetSize / 2**20,
        "private_mb": counters.PagefileUsage / 2**20,
    }
