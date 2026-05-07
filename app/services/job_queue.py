"""
Job Queue Service
Provides a shared in-process queue and worker pool for long-running GPR jobs.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from app.config import MAX_WORKERS, PROCESSED_FOLDER
from app.database import get_db
from app.services.gpr_processor import process_gpr_data, processing_jobs, update_job_status
from app.services.kml_parser import extract_kml_data
from app.services.shapefile_parser import extract_shapefile_data


JOB_QUEUE_WORKERS = max(1, min(2, MAX_WORKERS))


@dataclass(slots=True)
class QueuedJob:
    job_id: str
    filepath: str
    filename: str
    settings: Dict[str, Any]
    user_email: Optional[str] = None
    job_name: Optional[str] = None
    geo_path: Optional[str] = None
    queued_at: float = field(default_factory=time.time)


class JobQueueManager:
    def __init__(self) -> None:
        self._queue: "queue.Queue[Optional[QueuedJob]]" = queue.Queue()
        self._lock = threading.Lock()
        self._pending_order: "OrderedDict[str, QueuedJob]" = OrderedDict()
        self._active_jobs: set[str] = set()
        self._cancelled_jobs: set[str] = set()
        self._workers: list[threading.Thread] = []
        self._started = False
        self._stopping = False

    def start(self, worker_count: int = JOB_QUEUE_WORKERS) -> None:
        with self._lock:
            if self._started:
                return
            self._stopping = False
            for index in range(worker_count):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"gpr-job-worker-{index + 1}",
                    daemon=True,
                )
                worker.start()
                self._workers.append(worker)
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._stopping = True
            worker_count = len(self._workers)

        for _ in range(worker_count):
            self._queue.put(None)

        for worker in self._workers:
            worker.join(timeout=5)

        with self._lock:
            self._workers.clear()
            self._started = False
            self._stopping = False

    def enqueue(self, job: QueuedJob) -> Dict[str, Any]:
        self.start()

        with self._lock:
            self._pending_order[job.job_id] = job
            processing_jobs[job.job_id] = {
                "status": "queued",
                "message": "Waiting for an available worker...",
                "filename": job.filename,
                "settings": job.settings,
                "queued_at": job.queued_at,
                "queue_position": len(self._pending_order),
                "worker_count": len(self._workers),
            }

        self._queue.put(job)
        return self.snapshot(job.job_id)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._pending_order.pop(job_id, None)
            if not job:
                return False
            self._cancelled_jobs.add(job_id)
            processing_jobs[job_id] = {
                "status": "cancelled",
                "message": "Job was cancelled before processing started.",
                "filename": job.filename,
                "settings": job.settings,
                "queued_at": job.queued_at,
                "queue_position": 0,
                "worker_count": len(self._workers),
            }
            self._refresh_queue_positions_locked()
            return True

    def snapshot(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            snapshot = dict(processing_jobs.get(job_id, {}))
            queue_position = self._queue_position_locked(job_id)
            if queue_position is not None:
                snapshot["queue_position"] = queue_position
            snapshot["queued_jobs"] = len(self._pending_order)
            snapshot["active_jobs"] = len(self._active_jobs)
            snapshot["worker_count"] = len(self._workers)
            if job_id in self._cancelled_jobs:
                snapshot.setdefault("status", "cancelled")
                snapshot.setdefault("message", "Job was cancelled before processing started.")
            return snapshot

    def queue_depth(self) -> int:
        with self._lock:
            return len(self._pending_order)

    def _queue_position_locked(self, job_id: str) -> Optional[int]:
        for index, pending_job_id in enumerate(self._pending_order.keys(), start=1):
            if pending_job_id == job_id:
                return index
        return None

    def _refresh_queue_positions_locked(self) -> None:
        for index, job in enumerate(self._pending_order.values(), start=1):
            entry = processing_jobs.get(job.job_id)
            if entry:
                entry["queue_position"] = index
                entry["queued_jobs"] = len(self._pending_order)
                entry["worker_count"] = len(self._workers)

    def _mark_processing(self, job: QueuedJob) -> None:
        entry = processing_jobs.setdefault(job.job_id, {})
        entry.update(
            {
                "status": "processing",
                "message": "Worker started processing job...",
                "filename": job.filename,
                "settings": job.settings,
                "queued_at": job.queued_at,
                "queue_position": 0,
                "started_at": time.time(),
                "worker_count": len(self._workers),
            }
        )
        self._update_processed_job(job, status="processing", storage_path="pending")

    def _read_status_file(self, job_id: str) -> Dict[str, Any]:
        status_file = os.path.join(PROCESSED_FOLDER, job_id, "status.json")
        if not os.path.exists(status_file):
            return {}

        try:
            with open(status_file, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return {}

    def _update_processed_job(self, job: QueuedJob, status: str, storage_path: str) -> None:
        if not job.user_email:
            return

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO processed_jobs (job_id, user_email, job_name, processing_date, status, storage_path)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE SET
                    processing_date = EXCLUDED.processing_date,
                    status = EXCLUDED.status,
                    storage_path = EXCLUDED.storage_path,
                    job_name = EXCLUDED.job_name
                """,
                (
                    job.job_id,
                    job.user_email,
                    job.job_name or job.filename,
                    datetime.now(),
                    status,
                    storage_path,
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as exc:
            print(f"Error updating queued job row for {job.job_id}: {exc}")

    def _extract_geo_metadata(self, geo_path: str) -> tuple[Optional[dict], Optional[list]]:
        geo_ext = os.path.splitext(geo_path)[1].lower()
        if geo_ext == ".kml":
            geo_data = extract_kml_data(geo_path)
        elif geo_ext == ".zip":
            geo_data = extract_shapefile_data(geo_path)
        else:
            return None, None

        if not geo_data:
            return None, None

        return geo_data.get("center"), geo_data.get("points")

    def _apply_geo_metadata(self, job: QueuedJob) -> None:
        if not job.geo_path:
            return

        try:
            kml_anchor, kml_polygon = self._extract_geo_metadata(job.geo_path)
            if kml_anchor:
                job.settings["kml_anchor"] = kml_anchor
            if kml_polygon:
                job.settings["kml_polygon"] = kml_polygon
        except Exception as exc:
            print(f"Warning: failed to parse geo file for {job.job_id}: {exc}")

    def _worker_loop(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                self._queue.task_done()
                break

            with self._lock:
                if job.job_id in self._cancelled_jobs:
                    self._refresh_queue_positions_locked()
                    self._queue.task_done()
                    continue
                self._pending_order.pop(job.job_id, None)
                self._active_jobs.add(job.job_id)
                self._refresh_queue_positions_locked()

            try:
                self._mark_processing(job)
                self._apply_geo_metadata(job)
                processing_jobs[job.job_id].update({"settings": job.settings})
                process_gpr_data(job.job_id, job.filepath, job.settings, job.filename)

                final_snapshot = self._read_status_file(job.job_id)
                final_status = final_snapshot.get("status", "completed")
                final_message = final_snapshot.get("message", "Processing complete!")
                entry = processing_jobs.setdefault(job.job_id, {})
                entry.update(
                    {
                        "status": final_status,
                        "message": final_message,
                        "filename": job.filename,
                        "settings": job.settings,
                        "finished_at": time.time(),
                        "worker_count": len(self._workers),
                    }
                )
                if final_snapshot:
                    entry.update(final_snapshot)
            except Exception as exc:
                print(f"Worker error for {job.job_id}: {exc}")
                entry = processing_jobs.setdefault(job.job_id, {})
                entry.update(
                    {
                        "status": "error",
                        "message": f"Processing failed: {exc}",
                        "filename": job.filename,
                        "settings": job.settings,
                        "finished_at": time.time(),
                        "worker_count": len(self._workers),
                    }
                )
                self._update_processed_job(job, status="error", storage_path="pending")
                update_job_status(job.job_id, "error", f"Processing failed: {exc}")
            finally:
                with self._lock:
                    self._active_jobs.discard(job.job_id)
                self._queue.task_done()


job_queue_manager = JobQueueManager()


def start_job_queue(worker_count: int = JOB_QUEUE_WORKERS) -> None:
    job_queue_manager.start(worker_count)


def stop_job_queue() -> None:
    job_queue_manager.stop()


def enqueue_gpr_job(
    job_id: str,
    filepath: str,
    filename: str,
    settings: Dict[str, Any],
    user_email: Optional[str] = None,
    job_name: Optional[str] = None,
    geo_path: Optional[str] = None,
) -> Dict[str, Any]:
    job = QueuedJob(
        job_id=job_id,
        filepath=filepath,
        filename=filename,
        settings=dict(settings),
        user_email=user_email,
        job_name=job_name or filename,
        geo_path=geo_path,
    )
    return job_queue_manager.enqueue(job)


def cancel_queued_job(job_id: str) -> bool:
    return job_queue_manager.cancel(job_id)


def get_job_snapshot(job_id: str) -> Dict[str, Any]:
    snapshot = job_queue_manager.snapshot(job_id)
    status_file = os.path.join(PROCESSED_FOLDER, job_id, "status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as handle:
                disk_status = json.load(handle)
            snapshot.update(disk_status)
        except Exception:
            pass

    if not snapshot and not os.path.exists(status_file):
        return {}

    return snapshot


__all__ = [
    "JOB_QUEUE_WORKERS",
    "cancel_queued_job",
    "enqueue_gpr_job",
    "get_job_snapshot",
    "job_queue_manager",
    "start_job_queue",
    "stop_job_queue",
]
