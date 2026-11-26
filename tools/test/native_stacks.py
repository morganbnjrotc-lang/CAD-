"""Prints the native call stack of every thread of a running process (Windows x64), with names from its PDBs,
without a debugger: dbghelp's StackWalk64 on each thread, suspended for a moment and resumed.

For a FreeCAD that hangs (not responding, no CPU in use): run it on the RelWithDebInfo build, which has PDBs, and
    pixi run python tools/test/native_stacks.py <pid> [max frames]
The process keeps running. Found the preview deadlock of 2026-11-26 (docs/BASELINE.md)."""
import ctypes
import ctypes.wintypes as wt
import sys

pid = int(sys.argv[1])
MAX_FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 40

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
dbg = ctypes.WinDLL("dbghelp", use_last_error=True)

PROCESS_QUERY_INFORMATION, PROCESS_VM_READ = 0x0400, 0x0010
THREAD_ALL = 0x0002 | 0x0008 | 0x0040 | 0x0010  # suspend/resume, get context, query information
TH32CS_SNAPTHREAD = 0x4
CONTEXT_FULL = 0x10000B
IMAGE_FILE_MACHINE_AMD64 = 0x8664
SYMOPT_UNDNAME, SYMOPT_DEFERRED_LOADS, SYMOPT_LOAD_LINES = 0x2, 0x4, 0x10


class THREADENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ThreadID", wt.DWORD),
                ("th32OwnerProcessID", wt.DWORD), ("tpBasePri", ctypes.c_long), ("tpDeltaPri", ctypes.c_long),
                ("dwFlags", wt.DWORD)]


class ADDRESS64(ctypes.Structure):
    _fields_ = [("Offset", ctypes.c_uint64), ("Segment", ctypes.c_uint16), ("Mode", ctypes.c_int)]


class STACKFRAME64(ctypes.Structure):
    _fields_ = [("AddrPC", ADDRESS64), ("AddrReturn", ADDRESS64), ("AddrFrame", ADDRESS64),
                ("AddrStack", ADDRESS64), ("AddrBStore", ADDRESS64), ("FuncTableEntry", ctypes.c_void_p),
                ("Params", ctypes.c_uint64 * 4), ("Far", wt.BOOL), ("Virtual", wt.BOOL),
                ("Reserved", ctypes.c_uint64 * 3), ("KdHelp", ctypes.c_byte * 256)]


class SYMBOL_INFOW(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wt.ULONG), ("TypeIndex", wt.ULONG), ("Reserved", ctypes.c_uint64 * 2),
                ("Index", wt.ULONG), ("Size", wt.ULONG), ("ModBase", ctypes.c_uint64), ("Flags", wt.ULONG),
                ("Value", ctypes.c_uint64), ("Address", ctypes.c_uint64), ("Register", wt.ULONG),
                ("Scope", wt.ULONG), ("Tag", wt.ULONG), ("NameLen", wt.ULONG), ("MaxNameLen", wt.ULONG),
                ("Name", ctypes.c_wchar * 1024)]


class IMAGEHLP_LINEW64(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wt.DWORD), ("Key", ctypes.c_void_p), ("LineNumber", wt.DWORD),
                ("FileName", ctypes.c_wchar_p), ("Address", ctypes.c_uint64)]


k32.OpenProcess.restype = wt.HANDLE
k32.OpenThread.restype = wt.HANDLE
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
dbg.SymFunctionTableAccess64.restype = ctypes.c_void_p
dbg.SymFunctionTableAccess64.argtypes = [wt.HANDLE, ctypes.c_uint64]
dbg.SymGetModuleBase64.restype = ctypes.c_uint64
dbg.SymGetModuleBase64.argtypes = [wt.HANDLE, ctypes.c_uint64]
FTA = ctypes.WINFUNCTYPE(ctypes.c_void_p, wt.HANDLE, ctypes.c_uint64)(("SymFunctionTableAccess64", dbg))
GMB = ctypes.WINFUNCTYPE(ctypes.c_uint64, wt.HANDLE, ctypes.c_uint64)(("SymGetModuleBase64", dbg))
dbg.StackWalk64.argtypes = [wt.DWORD, wt.HANDLE, wt.HANDLE, ctypes.POINTER(STACKFRAME64), ctypes.c_void_p,
                            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
dbg.SymFromAddrW.argtypes = [wt.HANDLE, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(SYMBOL_INFOW)]
dbg.SymGetLineFromAddrW64.argtypes = [wt.HANDLE, ctypes.c_uint64, ctypes.POINTER(wt.DWORD),
                                      ctypes.POINTER(IMAGEHLP_LINEW64)]
dbg.SymInitializeW.argtypes = [wt.HANDLE, wt.LPCWSTR, wt.BOOL]
k32.GetThreadContext.argtypes = [wt.HANDLE, ctypes.c_void_p]
k32.GetModuleFileNameExW = ctypes.WinDLL("psapi").GetModuleFileNameExW

process = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
if not process:
    sys.exit(f"OpenProcess failed: {ctypes.get_last_error()}")
dbg.SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES)
if not dbg.SymInitializeW(process, None, True):
    sys.exit(f"SymInitialize failed: {ctypes.get_last_error()}")


def name_of(address):
    symbol = SYMBOL_INFOW()
    symbol.SizeOfStruct = ctypes.sizeof(SYMBOL_INFOW) - ctypes.sizeof(ctypes.c_wchar) * 1024 + 2
    symbol.MaxNameLen = 1023
    displacement = ctypes.c_uint64()
    base = dbg.SymGetModuleBase64(process, address)
    module = ctypes.create_unicode_buffer(260)
    k32.GetModuleFileNameExW(process, ctypes.c_void_p(base), module, 260) if base else None
    mod = module.value.rsplit("\\", 1)[-1] if base else "?"
    if dbg.SymFromAddrW(process, address, ctypes.byref(displacement), ctypes.byref(symbol)):
        text = f"{mod}!{symbol.Name}+0x{displacement.value:x}"
    else:
        text = f"{mod}+0x{address - base:x}" if base else f"0x{address:x}"
    line = IMAGEHLP_LINEW64()
    line.SizeOfStruct = ctypes.sizeof(IMAGEHLP_LINEW64)
    col = wt.DWORD()
    if dbg.SymGetLineFromAddrW64(process, address, ctypes.byref(col), ctypes.byref(line)):
        text += f"  [{line.FileName.rsplit(chr(92), 1)[-1]}:{line.LineNumber}]"
    return text


snapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
entry = THREADENTRY32()
entry.dwSize = ctypes.sizeof(THREADENTRY32)
threads = []
ok = k32.Thread32First(snapshot, ctypes.byref(entry))
while ok:
    if entry.th32OwnerProcessID == pid:
        threads.append(entry.th32ThreadID)
    ok = k32.Thread32Next(snapshot, ctypes.byref(entry))
k32.CloseHandle(snapshot)

for tid in threads:
    thread = k32.OpenThread(THREAD_ALL, False, tid)
    if not thread:
        print(f"== thread {tid}: OpenThread failed {ctypes.get_last_error()}")
        continue
    raw = ctypes.create_string_buffer(1232 + 16)
    address = (ctypes.addressof(raw) + 15) & ~15
    ctypes.c_uint32.from_address(address + 0x30).value = CONTEXT_FULL
    k32.SuspendThread(thread)
    try:
        if not k32.GetThreadContext(thread, ctypes.c_void_p(address)):
            print(f"== thread {tid}: GetThreadContext failed {ctypes.get_last_error()}")
            continue
        frame = STACKFRAME64()
        frame.AddrPC.Offset = ctypes.c_uint64.from_address(address + 0xF8).value
        frame.AddrFrame.Offset = ctypes.c_uint64.from_address(address + 0xA0).value
        frame.AddrStack.Offset = ctypes.c_uint64.from_address(address + 0x98).value
        for a in (frame.AddrPC, frame.AddrFrame, frame.AddrStack):
            a.Mode = 3  # flat
        lines = []
        for _ in range(MAX_FRAMES):
            if not dbg.StackWalk64(IMAGE_FILE_MACHINE_AMD64, process, thread, ctypes.byref(frame),
                                   ctypes.c_void_p(address), None, ctypes.cast(FTA, ctypes.c_void_p),
                                   ctypes.cast(GMB, ctypes.c_void_p), None):
                break
            if frame.AddrPC.Offset == 0:
                break
            lines.append("   " + name_of(frame.AddrPC.Offset))
    finally:
        k32.ResumeThread(thread)
        k32.CloseHandle(thread)
    print(f"== thread {tid} ({len(lines)} frames)")
    print("\n".join(lines))
dbg.SymCleanup(process)
k32.CloseHandle(process)
