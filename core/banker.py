"""Implementação simplificada do algoritmo do banqueiro para processos."""

import threading
from typing import List


class Banker:
    """Controla alocação de recursos usando o algoritmo do banqueiro."""

    def __init__(self, available: List[int], max_claims: List[List[int]]) -> None:
        self.resource_count = len(available)
        self.process_count = len(max_claims)
        self.available = list(available)
        self.max_claims = [list(row) for row in max_claims]
        self.allocation = [[0 for _ in range(self.resource_count)] for _ in range(self.process_count)]
        self.lock = threading.Lock()

    def request_resources(self, pid: int, request: List[int]) -> bool:
        """Tenta conceder o request; só aplica se o estado permanecer seguro."""
        if len(request) != self.resource_count or any(r < 0 for r in request):
            return False

        with self.lock:
            if not self._within_need(pid, request):
                return False
            if not self._fits_available(request):
                return False
            if not self._safe_if_granted(pid, request):
                return False
            for idx, amount in enumerate(request):
                self.available[idx] -= amount
                self.allocation[pid][idx] += amount
            return True

    def release_all(self, pid: int) -> List[int]:
        """Devolve todos os recursos que estavam alocados para o processo."""
        with self.lock:
            released: List[int] = []
            for idx in range(self.resource_count):
                amount = self.allocation[pid][idx]
                released.append(amount)
                self.available[idx] += amount
                self.allocation[pid][idx] = 0
            return released

    def snapshot(self) -> dict:
        """Retorna uma cópia simples do estado atual (para logs)."""
        with self.lock:
            return {
                "available": list(self.available),
                "allocation": [list(row) for row in self.allocation],
                "max_claims": [list(row) for row in self.max_claims],
            }


    def _within_need(self, pid: int, request: List[int]) -> bool:
        need = self._need_for(pid)
        return all(req <= n for req, n in zip(request, need))

    def _fits_available(self, request: List[int]) -> bool:
        return all(req <= avail for req, avail in zip(request, self.available))

    def _safe_if_granted(self, pid: int, request: List[int]) -> bool:
        available = list(self.available)
        allocation = [list(row) for row in self.allocation]
        max_claims = [list(row) for row in self.max_claims]

        for idx in range(self.resource_count):
            available[idx] -= request[idx]
            allocation[pid][idx] += request[idx]

        need = [
            [max_claims[p][r] - allocation[p][r] for r in range(self.resource_count)]
            for p in range(self.process_count)
        ]
        work = list(available)
        finish = [False for _ in range(self.process_count)]

        while True:
            progressed = False
            for proc in range(self.process_count):
                if finish[proc]:
                    continue
                if all(need_item <= work_res for need_item, work_res in zip(need[proc], work)):
                    for r_idx in range(self.resource_count):
                        work[r_idx] += allocation[proc][r_idx]
                    finish[proc] = True
                    progressed = True
            if not progressed:
                break

        return all(finish)

    def _need_for(self, pid: int) -> List[int]:
        return [max_r - alloc_r for max_r, alloc_r in zip(self.max_claims[pid], self.allocation[pid])]
