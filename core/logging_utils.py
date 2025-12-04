"""Funções auxiliares de logging e configuração do multiprocessing."""

import multiprocessing as mp
from datetime import datetime


def log(name: str, message: str) -> None:
    """Imprime uma linha com horário e nome do processo."""
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{now}] {name}: {message}", flush=True)


def configure_multiprocessing() -> None:
    """
    Força o start method para 'fork' (ou 'spawn' como fallback) para contornar
    ambientes que impõem 'forkserver' e quebram ao reconstruir SemLock.
    """
    supported = mp.get_all_start_methods()
    target = "fork" if "fork" in supported else ("spawn" if "spawn" in supported else None)
    current = mp.get_start_method(allow_none=True)
    if target and current != target:
        try:
            mp.set_start_method(target, force=True)
        except RuntimeError:
            # Já inicializado com outro método; mantenha-o.
            pass
