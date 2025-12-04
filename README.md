# Simulação de deadlock e formas de resolver

Pequeno laboratório em Python que mostra:
- um deadlock clássico entre dois processos competindo por dois recursos;
- como evitar o mesmo deadlock com ordenação global de locks;
- como recuperar com tentativa/timeout e backoff.

## Estrutura
- `deadlock_demo.py`: código principal com três cenários (deadlock, solução por ordenação e solução com retry).

## Requisitos
- Python 3.8+ (usa apenas biblioteca padrão).

## Como executar
No diretório do projeto:
```bash
python deadlock_demo.py           # roda os três cenários em sequência
python deadlock_demo.py deadlock  # roda só o cenário com deadlock detectado
python deadlock_demo.py ordenado  # prevenção com ordem fixa de aquisição
python deadlock_demo.py retry     # recuperação com timeout e backoff
```

## O que observar
- Deadlock: os processos P1 e P2 pegam os recursos em ordem inversa (A depois B vs. B depois A). Ambos ficam aguardando para sempre; o processo pai detecta que eles não terminaram em 5s e os mata, imprimindo uma mensagem de deadlock.
- Ordem fixa: ambos os processos respeitam a mesma ordem (A depois B), removendo o ciclo de espera e finalizando normalmente.
- Retry/timeout: mesmo começando com ordem invertida, cada processo aborta a tentativa se o segundo recurso não vier rápido, libera o que tem, espera um pouco e tenta de novo. Eventualmente um deles progride e ambos concluem.

## Ideias extras que cabem sem complexidade
- Ajuste a constante `HOLD_TIME` no início do arquivo para ver o efeito de tempos maiores/menores.
- Rode com mais processos (copiando o padrão das listas de processos) para visualizar como a ordenação global continua evitando deadlocks.
- Altere o `DEADLOCK_TIMEOUT` para ver a detecção mais cedo ou mais tarde.
