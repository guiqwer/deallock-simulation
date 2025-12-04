"""Cenários de concorrência para demonstrar deadlocks e soluções."""

import multiprocessing as mp
import time
from abc import ABC, abstractmethod
from typing import Iterable, List

from core.metrics import Metrics, collect_metrics, create_metrics_queue, summarize_metrics
from core.worker import NaiveWorker, RetryWorker, Worker


class Scenario(ABC):
    """Base para cenários de concorrência."""

    def __init__(self, title: str, show_progress: bool = False, workers: int = 2) -> None:
        self.title = title
        self.scenario_tag = self.title.split(":")[0].strip()
        self.show_progress = show_progress
        self.workers = workers

    def run(self) -> List[Metrics]:
        print(f"\n=== {self.title} ===")
        scenario_start = time.time()
        metrics_queue = create_metrics_queue()

        processes = self._spawn_workers(metrics_queue)
        self.wait_processes(processes, metrics_queue)
        duration = time.time() - scenario_start
        metrics = collect_metrics(metrics_queue)
        for metric in metrics:
            metric["scenario"] = self.title
            metric["cenario"] = self.scenario_tag  # rótulo curto
        self.after_finish()
        summarize_metrics(metrics, duration, [p.name for p in processes], self.scenario_tag)
        return metrics

    def _spawn_workers(self, metrics_queue: mp.Queue | None) -> List[mp.Process]:
        workers = self.build_workers(metrics_queue)
        processes = [mp.Process(target=worker.run, name=worker.name) for worker in workers]
        for process in processes:
            process.start()
        if self.show_progress:
            print(f"[PROGRESSO] {len(processes)}/{len(processes)} processos iniciados.")
        return processes

    def wait_processes(self, processes: Iterable[mp.Process], metrics_queue: mp.Queue | None) -> None:
        completed = 0
        processes = list(processes)
        total = len(processes)
        for process in processes:
            process.join()
            completed += 1
            self.report_progress(completed, total)

    def after_finish(self) -> None:
        """Hook para mensagens finais."""

    @abstractmethod
    def build_workers(self, metrics_queue: mp.Queue | None) -> List[Worker]:
        """Cria os workers que serão executados no cenário."""

    def report_progress(self, completed: int, total: int) -> None:
        if not self.show_progress:
            return
        print(f"[PROGRESSO] {completed}/{total} processos finalizados.")


class DeadlockScenario(Scenario):
    """Cria deadlock intencional para ser detectado."""

    def __init__(self, hold_time: float, timeout: float, show_progress: bool = False, workers: int = 2) -> None:
        super().__init__("CENÁRIO 1: Deadlock intencional", show_progress, workers)
        self.hold_time = hold_time
        self.timeout = timeout

    def build_workers(self, metrics_queue: mp.Queue | None) -> List[Worker]:
        lock_a = mp.Lock()
        lock_b = mp.Lock()
        workers: List[Worker] = []
        for idx in range(self.workers):
            # Alterna a ordem para manter o ciclo de espera circular.
            if idx % 2 == 0:
                first_lock, first_label = lock_a, "Recurso A"
                second_lock, second_label = lock_b, "Recurso B"
            else:
                first_lock, first_label = lock_b, "Recurso B"
                second_lock, second_label = lock_a, "Recurso A"

            workers.append(
                NaiveWorker(
                    f"P{idx + 1}",
                    first_lock,
                    first_label,
                    second_lock,
                    second_label,
                    self.hold_time,
                    metrics_queue,
                )
            )
        return workers

    def wait_processes(self, processes: Iterable[mp.Process], metrics_queue: mp.Queue | None) -> None:
        processes = list(processes)
        total = len(processes)
        completed = 0
        for process in processes:
            process.join(timeout=self.timeout)
            if not process.is_alive():
                completed += 1
                self.report_progress(completed, total)

        stuck = [process for process in processes if process.is_alive()]
        if stuck:
            print(
                f"\n[PAI] Deadlock detectado: processos {[p.name for p in stuck]} "
                f"continuam vivos após {self.timeout}s."
            )
            for process in stuck:
                process.terminate()
            for process in processes:
                process.join()
                if not process.is_alive():
                    completed += 1
                    self.report_progress(completed, total)
            print("[PAI] Finalizei processos presos para evitar travar a execução.\n")
        else:
            print("[PAI] Surpreendente! Eles terminaram (talvez o ambiente seja muito rápido).")


class OrderedScenario(Scenario):
    """Evita deadlock com ordem fixa na aquisição de recursos."""

    def __init__(self, hold_time: float, show_progress: bool = False, workers: int = 2) -> None:
        super().__init__("CENÁRIO 2: Prevenção com ordem fixa de aquisição", show_progress, workers)
        self.hold_time = hold_time

    def build_workers(self, metrics_queue: mp.Queue | None) -> List[Worker]:
        lock_a = mp.Lock()
        lock_b = mp.Lock()
        return [
            NaiveWorker(
                f"P{idx + 1}",
                lock_a,
                "Recurso A",
                lock_b,
                "Recurso B",
                self.hold_time,
                metrics_queue,
            )
            for idx in range(self.workers)
        ]

    def after_finish(self) -> None:
        print("[PAI] Ambos obedeceram a mesma ordem (A -> B) e finalizaram sem deadlock.\n")


class RetryScenario(Scenario):
    """Evita deadlock com timeout + backoff aleatório."""

    def __init__(self, hold_time: float, try_timeout: float, show_progress: bool = False, workers: int = 2) -> None:
        super().__init__("CENÁRIO 3: Recuperação com timeout + backoff", show_progress, workers)
        self.hold_time = hold_time
        self.try_timeout = try_timeout

    def build_workers(self, metrics_queue: mp.Queue | None) -> List[Worker]:
        lock_a = mp.Lock()
        lock_b = mp.Lock()
        workers: List[Worker] = []
        for idx in range(self.workers):
            if idx % 2 == 0:
                first_lock, first_label = lock_a, "Recurso A"
                second_lock, second_label = lock_b, "Recurso B"
            else:
                first_lock, first_label = lock_b, "Recurso B"
                second_lock, second_label = lock_a, "Recurso A"

            workers.append(
                RetryWorker(
                    f"P{idx + 1}",
                    first_lock,
                    first_label,
                    second_lock,
                    second_label,
                    self.hold_time,
                    self.try_timeout,
                    metrics_queue,
                )
            )
        return workers

    def after_finish(self) -> None:
        print("[PAI] Timeouts evitaram o deadlock mesmo com ordem inversa.\n")
