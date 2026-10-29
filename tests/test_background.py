import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

from rimprobe.background import BackgroundWorker


@unittest.skipUnless(os.name == "nt", "Win32 private desktop")
class BackgroundTests(unittest.TestCase):
    def test_native_child_is_on_private_desktop_without_input(self):
        script = """import ctypes
from ctypes import wintypes
user = ctypes.WinDLL('user32', use_last_error=True)
kernel = ctypes.WinDLL('kernel32')
user.GetThreadDesktop.argtypes = [wintypes.DWORD]
user.GetThreadDesktop.restype = wintypes.HANDLE
user.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
name = ctypes.create_unicode_buffer(512)
assert user.GetUserObjectInformationW(user.GetThreadDesktop(kernel.GetCurrentThreadId()), 2, name, ctypes.sizeof(name), None)
print(name.value, flush=True)
"""
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "child.log"
            worker = BackgroundWorker(uuid.uuid4().hex)
            try:
                with output_path.open("wb") as output:
                    process = worker.spawn([sys.executable, "-c", script], Path(directory), os.environ.copy(), output)
                self.assertEqual(process.wait(10), 0)
                self.assertEqual(output_path.read_text().strip(), worker.name)
                self.assertEqual(worker.evidence()["foreground_violations"], [])
            finally:
                worker.close()

    def test_resource_counters_are_for_owned_process_and_remain_cached_after_close(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = BackgroundWorker(uuid.uuid4().hex)
            try:
                with (Path(directory) / "child.log").open("wb") as output:
                    process = worker.spawn([sys.executable, "-c", "import time; time.sleep(30)"], Path(directory), os.environ.copy(), output)
                resources = worker.evidence()["resources"]
                self.assertTrue(resources["available"])
                self.assertFalse(resources["process_exited"])
                self.assertEqual(resources["measurement_errors"], [])
                self.assertGreater(resources["peak_working_set_bytes"], 0)
                self.assertGreater(resources["private_bytes"], 0)
                self.assertGreaterEqual(resources["cpu_seconds"], 0)
            finally:
                worker.close()
            cached = process.resource_sample()
            self.assertTrue(cached["cached"])
            self.assertEqual(cached["peak_working_set_bytes"], resources["peak_working_set_bytes"])

    def test_job_close_terminates_only_owned_child(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = BackgroundWorker(uuid.uuid4().hex)
            try:
                with (Path(directory) / "child.log").open("wb") as output:
                    process = worker.spawn([sys.executable, "-c", "import time; time.sleep(30)"], Path(directory), os.environ.copy(), output)
                self.assertIsNone(process.poll())
                worker.kernel32.CloseHandle(worker._job)
                worker._job = None
                self.assertIsInstance(process.wait(10), int)
            finally:
                worker.close()
