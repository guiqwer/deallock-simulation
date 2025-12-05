import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from .deadlock_detector import DeadlockDetector
from .lock_manager import LockManager
from .metrics import MetricsCollector
from .models import Process, ProcessState, Resource


class Simulator:
    # Main simulation loop with logging, state table, and deadlock detection.
    def __init__(
        self,
        processes: List[Process],
        resources: List[Resource],
        mode: str,
        max_steps: int = 50,
        output_format: str = "text",
    ):
        self.processes = processes
        self.resources: Dict[str, Resource] = {r.rid: r for r in resources}
        self.mode = mode
        self.output_format = output_format
        self.events: List[dict] = []
        self.state_history: List[dict] = []
        self.deadlock_info: Optional[dict] = None
        self.lock_manager = LockManager(self.resources, self.processes, mode, logger=self.log_event)
        self.detector = DeadlockDetector()
        self.metrics = MetricsCollector(mode, len(processes), len(resources))
        self.max_steps = max_steps

    def run(self) -> None:
        start_msg = (
            f"Running simulation with {len(self.processes)} processes and {len(self.resources)} resources in mode '{self.mode}'"
        )
        self.log_event(start_msg, t=0, kind="start", data={"mode": self.mode})
        deadlock_found = False
        for t in range(self.max_steps):
            deadlock_found = self.step(t)
            self.metrics.record_step(self.processes)
            if deadlock_found:
                break
            if all(p.state == ProcessState.FINISHED for p in self.processes):
                self.log_event(f"All processes finished by t={t}", t=t, kind="finish")
                break
        if self.output_format == "text":
            print(self.metrics.summary(self.processes))
        else:
            report = {
                "mode": self.mode,
                "metrics": self.metrics.as_dict(self.processes),
                "events": self.events,
                "state_history": self.state_history,
                "deadlock": self.deadlock_info,
            }
            os.makedirs("output", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join("output", f"{self.mode}_report_{timestamp}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print(f"JSON report saved to {path}")

    def step(self, t: int) -> bool:
        for process in self.processes:
            if process.state in (ProcessState.DEADLOCKED, ProcessState.FINISHED):
                continue
            if process.state == ProcessState.BLOCKED and process.current_request:
                self.lock_manager.request(process, process.current_request, t)
            elif process.state == ProcessState.RUNNING:
                if process.has_all_resources():
                    self._complete_process(process, t)
                    continue
                target = process.next_request(self.mode == "ordered")
                if target:
                    self.lock_manager.request(process, target, t)

        # After acquisition attempts, complete any process that now holds everything
        for process in self.processes:
            if process.state == ProcessState.RUNNING and process.has_all_resources():
                self._complete_process(process, t)

        deadlock, edges, cycle = self.detector.detect_deadlock(self.processes, self.resources)
        self.print_state_table(t)

        if deadlock:
            self.metrics.record_deadlock()
            self.deadlock_info = {"t": t, "edges": edges, "cycle": cycle}
            self.log_event(f"*** Deadlock detected at t={t} ***", t=t, kind="deadlock", data=self.deadlock_info)
            if self.output_format == "text":
                self.detector.print_wait_for_graph(edges, cycle)
            for pid in cycle:
                proc = self._process_by_id(pid)
                if proc:
                    proc.mark_deadlocked()
            return True
        return False

    def _complete_process(self, process: Process, t: int) -> None:
        self.log_event(
            f"[t={t}] {process.pid} completed its work; releasing resources",
            t=t,
            kind="complete",
            data={"pid": process.pid, "held": sorted(process.held_resources)},
        )
        self.lock_manager.release_all(process, t)
        self.metrics.record_completion()

    def _process_by_id(self, pid: str) -> Optional[Process]:
        for process in self.processes:
            if process.pid == pid:
                return process
        return None

    def print_state_table(self, t: int) -> None:
        snapshot = []
        for process in self.processes:
            held_list = sorted(process.held_resources)
            requested = process.current_request
            snapshot.append(
                {
                    "pid": process.pid,
                    "held": held_list,
                    "requested": requested,
                    "state": process.state.value,
                }
            )
        self.state_history.append({"t": t, "processes": snapshot})
        if self.output_format == "text":
            print("State table:")
            print("  t  | pid | held         | requested   | state")
            for row in snapshot:
                held_display = ",".join(row["held"]) if row["held"] else "-"
                requested_display = row["requested"] or "-"
                print(
                    f"  {t:02} | {row['pid']:>3} | {held_display:>11} | {requested_display:>11} | {row['state']}"
                )
            print("-")

    def log_event(self, message: str, t: int, kind: str = "info", data: Optional[dict] = None) -> None:
        entry = {"t": t, "kind": kind, "message": message}
        if data:
            entry["data"] = data
        self.events.append(entry)
        if self.output_format == "text":
            print(message)
