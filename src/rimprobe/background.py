import ctypes
from ctypes import wintypes
import os
import subprocess
import threading
import time
import msvcrt

from .errors import ProbeError


class BackgroundWorker:
    def __init__(self, session_id: str):
        if os.name != "nt":
            raise ProbeError("background_unsupported", "Strict background workers currently require Windows.")
        self.name = "RimProbe-" + session_id
        self._desktop = None
        self._job = None
        self._pid = None
        self._samples = 0
        self._violations = []
        self._stop = threading.Event()
        self._thread = None
        self._process = None
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p,
                                             wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
        self.user32.CreateDesktopW.restype = wintypes.HANDLE
        self.user32.CloseDesktop.argtypes = [wintypes.HANDLE]
        self.user32.CloseDesktop.restype = wintypes.BOOL
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel32.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.kernel32.GetProcessTimes.restype = wintypes.BOOL
        self.kernel32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD]
        self.kernel32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
        self.kernel32.CloseHandle.restype = wintypes.BOOL
        self.kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                                wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
                                                ctypes.c_void_p, ctypes.c_void_p]
        self.kernel32.CreateProcessW.restype = wintypes.BOOL
        self.kernel32.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                                                   ctypes.POINTER(ctypes.c_size_t)]
        self.kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        self.kernel32.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t,
                                                           ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
        self.kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
        self.kernel32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
        self.kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
        self.kernel32.ResumeThread.restype = wintypes.DWORD
        try:
            self._desktop = self.user32.CreateDesktopW(self.name, None, None, 0, 0x00C7, None)
            if not self._desktop:
                raise ctypes.WinError(ctypes.get_last_error())
            self._job = self.kernel32.CreateJobObjectW(None, None)
            if not self._job:
                raise ctypes.WinError(ctypes.get_last_error())
            information = ExtendedLimitInformation()
            information.BasicLimitInformation.LimitFlags = 0x2000
            if not self.kernel32.SetInformationJobObject(self._job, 9, ctypes.byref(information), ctypes.sizeof(information)):
                raise ctypes.WinError(ctypes.get_last_error())
        except OSError as error:
            self.close()
            raise ProbeError("background_unavailable", str(error)) from error

    def spawn(self, arguments: list[str], cwd, env: dict, output) -> "NativeProcess":
        startup = StartupInfoEx()
        startup.StartupInfo.cb = ctypes.sizeof(startup)
        startup.StartupInfo.lpDesktop = "WinSta0\\" + self.name
        startup.StartupInfo.dwFlags = 0x101
        startup.StartupInfo.wShowWindow = 0
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments))
        environment = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(env.items())) + "\0\0")
        information = ProcessInformation()
        attribute_size = ctypes.c_size_t()
        self.kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(attribute_size))
        attributes = ctypes.create_string_buffer(attribute_size.value)
        if not self.kernel32.InitializeProcThreadAttributeList(attributes, 1, 0, ctypes.byref(attribute_size)):
            raise ctypes.WinError(ctypes.get_last_error())
        startup.AttributeList = ctypes.cast(attributes, ctypes.c_void_p)
        output_handle = msvcrt.get_osfhandle(output.fileno())
        was_inheritable = os.get_handle_inheritable(output_handle)
        try:
            with open(os.devnull, "rb") as null_input:
                input_handle = msvcrt.get_osfhandle(null_input.fileno())
                os.set_handle_inheritable(input_handle, True)
                os.set_handle_inheritable(output_handle, True)
                handles = (wintypes.HANDLE * 2)(input_handle, output_handle)
                if not self.kernel32.UpdateProcThreadAttribute(attributes, 0, 0x20002, handles,
                                                               ctypes.sizeof(handles), None, None):
                    raise ctypes.WinError(ctypes.get_last_error())
                startup.StartupInfo.hStdInput = input_handle
                startup.StartupInfo.hStdOutput = output_handle
                startup.StartupInfo.hStdError = output_handle
                flags = 0x08000000 | 0x00004000 | 0x00000400 | 0x00080000 | 0x00000004
                if not self.kernel32.CreateProcessW(arguments[0], command, None, None, True, flags,
                                                     environment, str(cwd), ctypes.byref(startup), ctypes.byref(information)):
                    raise ctypes.WinError(ctypes.get_last_error())
            process = NativeProcess(information.hProcess, information.dwProcessId, arguments)
            self._process = process
            try:
                self.attach(process)
                if self.kernel32.ResumeThread(information.hThread) == 0xFFFFFFFF:
                    raise ctypes.WinError(ctypes.get_last_error())
            except (OSError, ProbeError):
                process.terminate()
                process.wait(10)
                raise
            finally:
                self.kernel32.CloseHandle(information.hThread)
            return process
        finally:
            os.set_handle_inheritable(output_handle, was_inheritable)
            self.kernel32.DeleteProcThreadAttributeList(attributes)

    def attach(self, process: subprocess.Popen) -> None:
        if not self.kernel32.AssignProcessToJobObject(self._job, int(process._handle)):
            raise ProbeError("job_assignment_failed", str(ctypes.WinError(ctypes.get_last_error())))
        self._pid = process.pid
        self._thread = threading.Thread(target=self._observe, name="RimProbe.FocusAudit", daemon=True)
        self._thread.start()

    def _observe(self) -> None:
        while not self._stop.is_set():
            window = self.user32.GetForegroundWindow()
            process_id = wintypes.DWORD()
            if window:
                self.user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
            self._samples += 1
            if process_id.value == self._pid and len(self._violations) < 10:
                self._violations.append({"elapsed_sample": self._samples, "code": "worker_in_foreground"})
            self._stop.wait(0.1)

    def evidence(self) -> dict:
        return {"mode": "isolated_windows_desktop", "desktop": self.name, "priority": "below_normal",
                "kill_on_controller_exit": True, "foreground_samples": self._samples,
                "foreground_violations": list(self._violations), "system_input_injection": False,
                "resources": self._process.resource_sample() if self._process is not None else {"available": False, "reason": "not_started"},
                "note": "Focus samples are supporting evidence, not a proof against every transient event."}

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._job:
            self.kernel32.CloseHandle(self._job)
            self._job = None
        try:
            if self._process is not None and self._process._handle:
                self._process.wait(timeout=10)
        finally:
            if self._desktop:
                self.user32.CloseDesktop(self._desktop)
                self._desktop = None
            if self._process is not None:
                self._process.close()


class NativeProcess:
    def __init__(self, handle, pid: int, arguments: list[str]):
        self._handle = handle
        self.pid = pid
        self.args = arguments
        self.returncode = None
        self._started = time.monotonic()
        self._resources = {}
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        self.kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel32.TerminateProcess.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    def resource_sample(self):
        result = dict(self._resources)
        errors = []
        if not self._handle:
            return dict(result, available=bool(result), cached=True, reason="handle_closed")
        created, exited, kernel, user = (wintypes.FILETIME() for index in range(4))
        if self.kernel32.GetProcessTimes(self._handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
            result["cpu_seconds"] = ((kernel.dwHighDateTime << 32) + kernel.dwLowDateTime
                                     + (user.dwHighDateTime << 32) + user.dwLowDateTime) / 10000000
        else:
            errors.append("GetProcessTimes:" + str(ctypes.get_last_error()))
        if self.poll() is None:
            memory = ProcessMemoryCounters()
            memory.cb = ctypes.sizeof(memory)
            if self.kernel32.K32GetProcessMemoryInfo(self._handle, ctypes.byref(memory), memory.cb):
                result["working_set_bytes"] = memory.WorkingSetSize
                result["peak_working_set_bytes"] = memory.PeakWorkingSetSize
                result["private_bytes"] = memory.PrivateUsage
                result["memory_sample_elapsed_seconds"] = round(time.monotonic() - self._started, 3)
            else:
                errors.append("K32GetProcessMemoryInfo:" + str(ctypes.get_last_error()))
        self._resources = result
        return dict(result, available=bool(result), elapsed_wall_seconds=round(time.monotonic() - self._started, 3),
                    process_exited=self.returncode is not None, measurement_errors=errors,
                    scope="Owned process only; cumulative CPU and OS memory counters, not Agent overhead, GPU use or foreground-game impact.")

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        result = self.kernel32.WaitForSingleObject(self._handle, 0)
        if result == 258:
            return None
        if result != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        exit_code = wintypes.DWORD()
        if not self.kernel32.GetExitCodeProcess(self._handle, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.returncode = exit_code.value
        return self.returncode

    def wait(self, timeout: float = 10):
        result = self.kernel32.WaitForSingleObject(self._handle, max(0, min(0xFFFFFFFE, int(timeout * 1000))))
        if result == 258:
            raise subprocess.TimeoutExpired(self.args, timeout)
        if result != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        return self.poll()

    def terminate(self):
        if self.poll() is None and not self.kernel32.TerminateProcess(self._handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def kill(self):
        self.terminate()

    def close(self):
        if self._handle:
            self.kernel32.CloseHandle(self._handle)
            self._handle = None


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
        "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage",
        "PeakPagefileUsage", "PrivateUsage")]


class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD),
                ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p),
                ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]


class StartupInfoEx(ctypes.Structure):
    _fields_ = [("StartupInfo", StartupInfo), ("AttributeList", ctypes.c_void_p)]


class ProcessInformation(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


class BasicLimitInformation(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
               ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", BasicLimitInformation), ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
