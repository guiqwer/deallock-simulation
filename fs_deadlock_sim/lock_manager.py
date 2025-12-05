from typing import Callable, Dict, List, Optional, Set

from .models import Process, ProcessState, Resource


class LockManager:
    """Simple lock manager for exclusive resource ownership (with optional Banker's algorithm)."""

    def __init__(
        self,
        resources: Dict[str, Resource],
        processes: List[Process],
        mode: str = "naive",
        logger: Optional[Callable[[str, int, str, Optional[dict]], None]] = None,
    ):
        self.resources = resources
        self.processes = processes
        self.mode = mode
        self.logger = logger

    def request(self, process: Process, resource_id: str, t: int) -> bool:
        if self.mode == "banker":
            return self._request_banker(process, resource_id, t)
        return self._request_basic(process, resource_id, t)

    def _request_basic(self, process: Process, resource_id: str, t: int) -> bool:
        resource = self.resources[resource_id]
        if resource.held_by is None:
            resource.held_by = process.pid
            process.held_resources.add(resource_id)
            process.state = ProcessState.RUNNING
            process.current_request = None
            self._log(f"[t={t}] {process.pid} acquired {resource_id}", t, "acquire", {"pid": process.pid, "resource": resource_id})
            return True
        if resource.held_by == process.pid:
            return True
        process.mark_blocked(resource_id)
        self._log(
            f"[t={t}] {process.pid} requested {resource_id} but it is held by {resource.held_by}; BLOCKED",
            t,
            "blocked",
            {"pid": process.pid, "resource": resource_id, "held_by": resource.held_by},
        )
        return False

    def _request_banker(self, process: Process, resource_id: str, t: int) -> bool:
        resource = self.resources[resource_id]
        if resource.held_by == process.pid:
            return True
        if resource.held_by is None:
            if self._is_safe_to_grant(process, resource_id):
                resource.held_by = process.pid
                process.held_resources.add(resource_id)
                process.state = ProcessState.RUNNING
                process.current_request = None
                self._log(
                    f"[t={t}] {process.pid} acquired {resource_id} (Banker's safe)",
                    t,
                    "acquire",
                    {"pid": process.pid, "resource": resource_id, "banker_safe": True},
                )
                return True
            process.mark_blocked(resource_id)
            self._log(
                f"[t={t}] {process.pid} requested {resource_id} but grant is unsafe by Banker's algorithm; BLOCKED",
                t,
                "blocked",
                {"pid": process.pid, "resource": resource_id, "held_by": None, "banker_safe": False},
            )
            return False

        process.mark_blocked(resource_id)
        self._log(
            f"[t={t}] {process.pid} requested {resource_id} but it is held by {resource.held_by}; BLOCKED",
            t,
            "blocked",
            {"pid": process.pid, "resource": resource_id, "held_by": resource.held_by},
        )
        return False

    def _is_safe_to_grant(self, process: Process, resource_id: str) -> bool:
        simulated_held: Dict[str, Set[str]] = {
            p.pid: set(p.held_resources) for p in self.processes if p.state != ProcessState.FINISHED
        }
        simulated_held.setdefault(process.pid, set(process.held_resources))
        simulated_held[process.pid].add(resource_id)

        available: Set[str] = {rid for rid, res in self.resources.items() if res.held_by is None}
        available.discard(resource_id)

        unfinished: Set[str] = {p.pid for p in self.processes if p.state != ProcessState.FINISHED}
        progress = True
        while progress:
            progress = False
            for proc in self.processes:
                if proc.pid not in unfinished:
                    continue
                held = simulated_held.get(proc.pid, set())
                needed = set(proc.plan) - held
                if needed.issubset(available):
                    progress = True
                    unfinished.remove(proc.pid)
                    available.update(held)
                    break

        return not unfinished

    def release_all(self, process: Process, t: int) -> None:
        if process.held_resources:
            held = ", ".join(sorted(process.held_resources))
            self._log(
                f"[t={t}] {process.pid} releasing {held}",
                t,
                "release",
                {"pid": process.pid, "resources": sorted(process.held_resources)},
            )
        for res_id in list(process.held_resources):
            resource = self.resources[res_id]
            if resource.held_by == process.pid:
                resource.held_by = None
        process.held_resources.clear()
        process.current_request = None
        process.state = ProcessState.FINISHED

    def _log(self, message: str, t: int, kind: str, data: Optional[dict] = None) -> None:
        if self.logger:
            self.logger(message, t, kind, data or {})
