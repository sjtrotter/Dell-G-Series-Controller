import tempfile
import unittest
from pathlib import Path

from src.service_status import acquire_service_lock, service_is_running


class ServiceStatusTest(unittest.TestCase):
    def test_reports_a_held_service_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service.lock"
            handle = acquire_service_lock(path)
            try:
                self.assertTrue(service_is_running(path))
            finally:
                handle.close()
            self.assertFalse(service_is_running(path))

    def test_rejects_a_second_service(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service.lock"
            handle = acquire_service_lock(path)
            try:
                with self.assertRaisesRegex(RuntimeError, "already running"):
                    acquire_service_lock(path)
            finally:
                handle.close()

    def test_an_unlocked_stale_file_is_not_running(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service.lock"
            path.write_text("1234\n", encoding="utf-8")
            self.assertFalse(service_is_running(path))
