"""Portable containment for the calculation worker.

The safe parser is the security boundary. This module is the next layer: it
keeps a damaged/bypassed parser from turning the worker into an unbounded host
process. It deliberately sticks to facilities that exist on all three target
platforms:

* the worker is already a separate process (``ProcessBackend``);
* its environment is reduced to the system paths it needs after interpreter
  startup;
* POSIX workers get hard ``resource`` limits (CPU, address space, file size,
  descriptors, core dumps);
* Windows workers are put in a Job Object with memory/CPU limits, one active
  process and desktop isolation, killed when the parent closes the job.

**What this does not do:** it does not deny filesystem or network access. Those
are capability sandboxes (Windows AppContainer, Linux Landlock/seccomp, macOS
sandbox profiles, or a WASM/WASI worker). They are intentionally not faked here:
a Python audit hook or a monkey-patched ``open`` is not a boundary. If a future
request needs "no files, no network", that has to be a platform-specific
backend, not this resource-containment layer.
"""

import os
import sys
from dataclasses import dataclass

#: Seconds of CPU a worker may consume before the OS kills it. The request
#: deadline is usually much shorter; this is the backstop.
DEFAULT_CPU_SECONDS = 300

#: Address-space and Job Object memory cap. SymPy itself needs far less; this
#: leaves room for a large symbolic result without allowing an unbounded one.
DEFAULT_MEMORY_BYTES = 1024 * 1024 * 1024

#: No calculation writes files. This bounds an accidental/damaged write and
#: gives the OS a reason to stop a runaway one.
DEFAULT_FILE_BYTES = 32 * 1024 * 1024

DEFAULT_OPEN_FILES = 64


@dataclass(frozen=True)
class Limits:
    """The resource budget shared by the child and the Windows job."""

    cpu_seconds: int = DEFAULT_CPU_SECONDS
    memory_bytes: int = DEFAULT_MEMORY_BYTES
    file_bytes: int = DEFAULT_FILE_BYTES
    open_files: int = DEFAULT_OPEN_FILES


DEFAULT_LIMITS = Limits()

#: Variables kept after the worker has imported its modules. The worker may
#: resolve fonts from the platform directories and use ``tempfile`` for an
#: extracted collection font, so those locations stay; secrets do not.
_ENV_KEEP_WINDOWS = frozenset({
    "SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP",
    "USERPROFILE", "LOCALAPPDATA", "APPDATA",
})
_ENV_KEEP_POSIX = frozenset({
    "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
})


def _sanitize_environment() -> None:
    keep = _ENV_KEEP_WINDOWS if sys.platform == "win32" else _ENV_KEEP_POSIX
    for key in tuple(os.environ):
        if key not in keep:
            os.environ.pop(key, None)
    try:
        os.umask(0o077)
    except OSError:
        pass


def _set_limit(resource_module, name: str, soft: int, hard: int | None = None) -> None:
    """Set one rlimit; absence/denial is not a worker failure."""
    limit = getattr(resource_module, name, None)
    if limit is None:
        return
    try:
        resource_module.setrlimit(limit, (soft, soft if hard is None else hard))
    except (OSError, ValueError):
        pass


def apply_worker_limits(limits: Limits = DEFAULT_LIMITS) -> None:
    """Apply what can be applied from inside the worker.

    Called once, after the worker imported its modules and before it serves the
    first request. Windows' job-wide restrictions are applied by the parent
    (``ProcessBackend``) because a child cannot assign itself.
    """
    _sanitize_environment()
    if sys.platform == "win32":
        return

    try:
        import resource
    except ImportError:
        return

    _set_limit(resource, "RLIMIT_CPU", limits.cpu_seconds, limits.cpu_seconds + 1)
    _set_limit(resource, "RLIMIT_AS", limits.memory_bytes)
    _set_limit(resource, "RLIMIT_FSIZE", limits.file_bytes)
    _set_limit(resource, "RLIMIT_NOFILE", limits.open_files)
    _set_limit(resource, "RLIMIT_CORE", 0)


class WindowsJob:
    """A Win32 Job Object holding one disposable calculation worker."""

    # JobObjectExtendedLimitInformation / JobObjectBasicUIRestrictions
    _EXTENDED_INFO = 9
    _UI_RESTRICTIONS = 4

    _LIMIT_PROCESS_TIME = 0x00000002
    _LIMIT_ACTIVE_PROCESS = 0x00000008
    _LIMIT_PROCESS_MEMORY = 0x00000100
    _LIMIT_JOB_MEMORY = 0x00000200
    _LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400
    _LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

    _UI_ALL = 0x00FF

    _PROCESS_TERMINATE = 0x0001
    _PROCESS_SET_QUOTA = 0x0100

    def __init__(self, limits: Limits) -> None:
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class UI_RESTRICTIONS(ctypes.Structure):
            _fields_ = [("UIRestrictionsClass", wintypes.DWORD)]

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._handle = None

        kernel32 = self._kernel32
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.SetInformationJobObject.argtypes = (
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
        )
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = (
            wintypes.HANDLE, wintypes.HANDLE
        )
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")

        info = EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.PerProcessUserTimeLimit = (
            limits.cpu_seconds * 10_000_000
        )
        info.BasicLimitInformation.LimitFlags = (
            self._LIMIT_PROCESS_TIME
            | self._LIMIT_ACTIVE_PROCESS
            | self._LIMIT_PROCESS_MEMORY
            | self._LIMIT_JOB_MEMORY
            | self._LIMIT_DIE_ON_UNHANDLED_EXCEPTION
            | self._LIMIT_KILL_ON_JOB_CLOSE
        )
        info.BasicLimitInformation.ActiveProcessLimit = 1
        info.ProcessMemoryLimit = limits.memory_bytes
        info.JobMemoryLimit = limits.memory_bytes
        if not kernel32.SetInformationJobObject(
            handle, self._EXTENDED_INFO, ctypes.byref(info), ctypes.sizeof(info)
        ):
            error = ctypes.get_last_error()
            kernel32.CloseHandle(handle)
            raise OSError(error, "SetInformationJobObject failed")

        ui = UI_RESTRICTIONS(self._UI_ALL)
        kernel32.SetInformationJobObject(
            handle, self._UI_RESTRICTIONS, ctypes.byref(ui), ctypes.sizeof(ui)
        )
        self._handle = handle

    def assign(self, pid: int) -> bool:
        """Put ``pid`` in this job. False means the process is not contained."""
        if self._handle is None:
            return False
        kernel32 = self._kernel32
        kernel32.OpenProcess.restype = self._wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (
            self._wintypes.DWORD, self._wintypes.BOOL, self._wintypes.DWORD
        )
        process = kernel32.OpenProcess(
            self._PROCESS_SET_QUOTA | self._PROCESS_TERMINATE, False, pid
        )
        if not process:
            return False
        try:
            return bool(kernel32.AssignProcessToJobObject(self._handle, process))
        finally:
            kernel32.CloseHandle(process)

    def close(self) -> None:
        """Close the job; ``KILL_ON_JOB_CLOSE`` terminates its worker."""
        handle, self._handle = self._handle, None
        if handle is not None:
            self._kernel32.CloseHandle(handle)


def create_job(limits: Limits = DEFAULT_LIMITS) -> WindowsJob | None:
    """Create the platform job, or None where the platform has no Job Object."""
    if sys.platform != "win32":
        return None
    try:
        return WindowsJob(limits)
    except OSError:
        return None
