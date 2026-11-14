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


# Every throwaway profile is brand-new except for one setting: the "Invalid OpenGL Version" warning
# counts as dismissed ("don't show again"). Release builds show that modal warning at startup when
# only OpenGL 1.x is available (src/Gui/StartupProcess.cpp, checkOpenGL), as on GitHub's GPU-less
# Windows runners. It never shows on a machine with a real GPU, so this changes nothing there.
_ALWAYS = {"BaseApp/CheckMessages/FreeCAD_-_Invalid_OpenGL_Version": True}


def _user_cfg(settings: dict) -> str:
    """A FreeCAD user.cfg holding `settings`: {"Group/Path/Name": str or bool} under Root."""
    from xml.etree import ElementTree

    root = ElementTree.Element("FCParameters")
    top = ElementTree.SubElement(root, "FCParamGroup", Name="Root")
    for key, value in settings.items():
        *groups, name = key.split("/")
        parent = top
        for group in groups:
            found = parent.find(f"FCParamGroup[@Name='{group}']")
            parent = found if found is not None else ElementTree.SubElement(parent, "FCParamGroup", Name=group)
        if type(value) is bool:
            ElementTree.SubElement(parent, "FCBool", Name=name, Value="1" if value else "0")
        elif type(value) is str:
            ElementTree.SubElement(parent, "FCText", Name=name).text = value
        else:
            raise TypeError(f"{key}: only text and true/false settings, got {type(value).__name__}")
    ElementTree.indent(root)
    return '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n' + ElementTree.tostring(
        root, encoding="unicode") + "\n"


def make_profile(root: Path, settings: dict | None = None) -> dict:
    """Creates a throwaway FreeCAD profile under `root`; returns the environment variables for it.

    `settings` ({"BaseApp/Preferences/General/Language": "English", ...}) are written to the
    profile's user.cfg before FreeCAD starts, for preferences that must hold from the first moment.

    Isolates home, data AND temp: FreeCAD keeps lock files in its temp cache, and sharing it with
    another running FreeCAD (e.g. a test run) can make that process wait forever. FreeCAD silently
    ignores these variables unless the folders already exist.
    """
    content = _user_cfg({**_ALWAYS, **(settings or {})})
    for sub in ("home", "data", "temp"):
        (root / sub).mkdir()
    (root / "home" / "user.cfg").write_text(content, encoding="utf-8")
    return {
        "FREECAD_USER_HOME": str(root / "home"),
        "FREECAD_USER_DATA": str(root / "data"),
        "FREECAD_USER_TEMP": str(root / "temp"),
    }


def run_probe(exe: Path, probe: Path, env: dict, timeout: float, tail: bool = False,
              settings: dict | None = None) -> dict:
    """Runs `exe probe` in a fresh throwaway FreeCAD profile and returns the JSON the probe wrote.

    The probe writes its result to the file named in STUDIO_BENCH_OUT. The returned dict also
    has "launched": the wall-clock time just before the process started. With `tail`, it also
    has "log": FreeCAD's log as [seconds since launch, line] pairs, stamped as written (see
    tail_log). Watching the log costs a little CPU, so the benchmarks leave it off. `settings`
    go into the profile before startup (see make_profile).
    """
    with tempfile.TemporaryDirectory(prefix="studio-bench-") as tmp:
        tmp = Path(tmp)
        out = tmp / "result.json"
        full_env = dict(os.environ)
        full_env.update(make_profile(tmp, settings), STUDIO_BENCH_OUT=str(out), **env)
        log = tmp / "freecad.log"
        console = tmp / "console.txt"
        lines = None
        with open(console, "wb") as console_out:
            launched = time.time()
            start = time.perf_counter()
            proc = subprocess.Popen(
                [str(exe), "--log-file", str(log), str(probe)],
                env=full_env,
                stdout=console_out,
                stderr=subprocess.STDOUT,
            )
            try:
                if tail:
                    lines = tail_log(log, proc, start, timeout)
                proc.wait(timeout=max(timeout - (time.perf_counter() - start), 0))
                status = f"exit code {proc.returncode}"
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                status = f"killed after {timeout} s"
            finally:
                # FreeCAD can relaunch itself as a detached process (e.g. one-time first-run
                # setup); that copy outlives the one we started, so close anything still running
                # our probe.
                kill_leftover(probe.name)
        if not out.exists():
            output = console.read_text(encoding="utf-8", errors="replace")
            log_tail = log.read_text(encoding="utf-8", errors="replace")[-3000:] if log.exists() else ""
            raise RuntimeError(
                f"probe did not report ({status})\n"
                f"--- stdout/stderr ---\n{output[-2000:]}\n"
                f"--- FreeCAD log ---\n{log_tail}"
            )
        data = json.loads(out.read_text(encoding="utf-8"))
        data["launched"] = launched
        if lines is not None:
            data["log"] = lines
        return data


def tail_log(path: Path, proc: subprocess.Popen, start: float, timeout: float | None = None) -> list:
    """Follows a log file while `proc` runs; returns [(seconds since `start`, line), ...].

    FreeCAD flushes its log file after every message, so stamping each line as soon as it shows
    up in the file gives its time to within about a millisecond (the file is checked every
    0.5 ms). Lines that arrive in one read share a timestamp. Raises subprocess.TimeoutExpired
    if `proc` is still running after `timeout` seconds.
    """
    lines, pending, position = [], "", 0
    while True:
        running = proc.poll() is None
        if path.exists():
            with open(path, encoding="utf-8", errors="replace") as f:
                f.seek(position)
                chunk = f.read()
                position = f.tell()
            if chunk:
                now = time.perf_counter() - start
                pending += chunk
                *complete, pending = pending.split("\n")
                lines += [(now, line.rstrip("\r")) for line in complete]
        if not running:
            break
        if timeout is not None and time.perf_counter() - start > timeout:
            raise subprocess.TimeoutExpired(proc.args, timeout)
        time.sleep(0.0005)
    if pending:
        lines.append((time.perf_counter() - start, pending.rstrip("\r")))
    return lines


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
