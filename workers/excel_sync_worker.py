"""
FinTrack - Smart Digital Banking & Loan Management System
Real-Time Auto-Updating Excel Workbook Synchronization Daemon
File: workers/excel_sync_worker.py

Continuously monitors PostgreSQL (fintrack) for any data mutations across all
8 relational tables and atomically refreshes `fintrack_live_data.xlsx` whenever
anything changes.
"""

import argparse
import logging
from pathlib import Path
import signal
import sys
import threading
import time

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.excel_service import DEFAULT_EXCEL_PATH, ExcelService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ExcelSync] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ExcelSyncWorker:
    """Watches PostgreSQL for any data change and keeps fintrack_live_data.xlsx live."""

    def __init__(self, output_path: Path = DEFAULT_EXCEL_PATH, poll_interval: float = 2.0):
        self.output_path = Path(output_path)
        self.poll_interval = poll_interval
        self._running = True
        self._last_fingerprint = None

        try:
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGINT, self._handle_shutdown)
                signal.signal(signal.SIGTERM, self._handle_shutdown)
        except (ValueError, AttributeError):
            pass

    def _handle_shutdown(self, signum, frame):
        logger.info("Shutdown signal received (%s). Stopping Excel sync worker...", signum)
        self._running = False

    def sync_if_changed(self, force: bool = False) -> bool:
        """
        Check PostgreSQL state fingerprint; regenerate workbook only if data changed or forced.
        Returns True if workbook was updated.
        """
        current_fp = ExcelService.compute_database_fingerprint()
        if force or current_fp != self._last_fingerprint or not self.output_path.exists():
            start = time.time()
            ExcelService.sync_live_workbook_to_disk(self.output_path)
            elapsed_ms = (time.time() - start) * 1000
            self._last_fingerprint = current_fp
            logger.info(
                "Synced live Excel workbook -> %s (%.1f ms, fp=%s)",
                self.output_path.name,
                elapsed_ms,
                current_fp[:10],
            )
            return True
        return False

    def run_loop(self) -> None:
        """Continuous live-sync polling loop."""
        logger.info(
            "Starting FinTrack Live Excel Auto-Sync Daemon (interval=%.1fs, target=%s)...",
            self.poll_interval,
            self.output_path,
        )
        # Immediate initial sync on startup
        try:
            self.sync_if_changed(force=True)
        except Exception as exc:
            logger.error("Initial Excel sync failed (will retry): %s", exc)

        while self._running:
            try:
                self.sync_if_changed(force=False)
            except Exception as exc:
                logger.error("Error during Excel live sync pass: %s", exc)

            # Interruptible sleep
            sleep_steps = max(1, int(self.poll_interval / 0.25))
            for _ in range(sleep_steps):
                if not self._running:
                    break
                time.sleep(0.25)

        logger.info("FinTrack Live Excel Auto-Sync Daemon shut down cleanly.")


def main():
    parser = argparse.ArgumentParser(description="FinTrack Real-Time Excel Workbook Sync Daemon")
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_EXCEL_PATH),
        help=f"Target Excel workbook path (default: {DEFAULT_EXCEL_PATH})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Generate the Excel workbook once and exit",
    )
    args = parser.parse_args()

    worker = ExcelSyncWorker(output_path=Path(args.output), poll_interval=args.interval)
    if args.once:
        worker.sync_if_changed(force=True)
    else:
        worker.run_loop()


if __name__ == "__main__":
    main()
