"""Workers que competem por recursos, com suporte a métricas."""

import multiprocessing as mp
import random
import time
from abc import ABC, abstractmethod
from typing import Optional

from core.logging_utils import log
from core.metrics import Metrics


class Worker(ABC):
    """Interface comum para workers que competem por recursos compartilhados."""

    def __init__(
        self,
        name: str,
        first_lock: mp.Lock,
        first_label: str,
        second_lock: mp.Lock,
        second_label: str,
        hold_time: float,
        metrics_queue: Optional[mp.Queue] = None,
    ) -> None:
        self.name = name
        self.first_lock = first_lock
        self.first_label = first_label
        self.second_lock = second_lock
        self.second_label = second_label
        self.hold_time = hold_time
        self.metrics_queue = metrics_queue
        self.started_at: float | None = None
        self.retries = 0

    def log(self, message: str) -> None:
        log(self.name, message)

    def record_start(self) -> None:
        self.started_at = time.time()

    def record_end(self, status: str = "ok") -> None:
        if self.metrics_queue is None:
            return
        ended_at = time.time()
        duration = round(ended_at - self.started_at, 3) if self.started_at else None
        payload: Metrics = {
            "name": self.name,
            "status": status,
            "retries": self.retries,
            "duration": duration,
        }
        self.metrics_queue.put(payload)

    def increment_retry(self) -> None:
        self.retries += 1

    @abstractmethod
    def run(self) -> None:
        """Fluxo específico de trabalho de cada cenário."""


class NaiveWorker(Worker):
    """Implementação que pode cair em deadlock."""

    def run(self) -> None:
        self.record_start()
        try:
            self.log(f"precisa do {self.first_label}")
            with self.first_lock:
                self.log(f"pegou {self.first_label}, trabalhando...")
                time.sleep(self.hold_time)
                self.log(f"tentando também o {self.second_label}")
                self.second_lock.acquire()
                self.log(f"pegou {self.second_label}, terminou trabalho conjunto")
                time.sleep(self.hold_time)
                self.second_lock.release()
                self.log(f"liberou {self.second_label}")
            self.log(f"liberou {self.first_label} e finalizou")
            self.record_end("ok")
        except Exception:
            self.record_end("erro")
            raise


class RetryWorker(Worker):
    """Implementação que evita deadlock com timeout e backoff."""

    def __init__(
        self,
        name: str,
        first_lock: mp.Lock,
        first_label: str,
        second_lock: mp.Lock,
        second_label: str,
        hold_time: float,
        try_timeout: float,
        metrics_queue: Optional[mp.Queue] = None,
    ) -> None:
        super().__init__(name, first_lock, first_label, second_lock, second_label, hold_time, metrics_queue)
        self.try_timeout = try_timeout
        self._rng = random.Random(name)  # base determinista por nome

    def run(self) -> None:
        self.record_start()
        try:
            while True:
                self.log(f"precisa do {self.first_label}")
                got_first = self.first_lock.acquire(timeout=self.try_timeout)
                if not got_first:
                    self.increment_retry()
                    self.log(f"não conseguiu {self.first_label} em {self.try_timeout}s, tentando de novo")
                    continue

                self.log(f"pegou {self.first_label}, agora quer o {self.second_label}")
                time.sleep(self.hold_time)
                got_second = self.second_lock.acquire(timeout=self.try_timeout)

                if got_second:
                    self.log(f"pegou {self.second_label}, fez o trabalho e vai liberar ambos")
                    time.sleep(self.hold_time)
                    self.second_lock.release()
                    self.first_lock.release()
                    self.log("liberou recursos e finalizou sem deadlock")
                    self.record_end("ok")
                    break

                self.increment_retry()
                self.log(f"timeout aguardando {self.second_label}, devolvendo {self.first_label}")
                self.first_lock.release()
                sleep_for = self.hold_time / 2 + self._rng.uniform(0, self.hold_time / 2)
                time.sleep(sleep_for)
        except Exception:
            self.record_end("erro")
            raise
