# ADR-001 — Monólito modular com workers Celery

**Status:** Aceita · **Data:** 2026-11-19

## Contexto
A plataforma tem ~15 módulos lógicos, mas um único desenvolvedor, volume de dados moderado (centenas de estações, observações horárias/10 min) e nenhuma exigência de escala independente por módulo.

## Problema
Como organizar o backend para manter limites claros sem pagar o custo operacional de sistemas distribuídos?

## Opções consideradas
1. **Microserviços** — isolamento forte; custo alto de deploy, observabilidade, contratos e consistência.
2. **Monólito sem fronteiras** — rápido no início; acoplamento cresce e dificulta evolução.
3. **Monólito modular + workers separados** — um deploy de API, processos de background independentes, fronteiras por pacote.

## Decisão
Opção 3. FastAPI única para a API; Celery workers (ingestão, processamento, relatórios, simulação) como processos separados que compartilham o mesmo código e banco.

## Justificativa
Atende à exigência de não introduzir microserviços cedo, mantém tarefas longas fora do ciclo de requisição e permite extrair um módulo no futuro se houver necessidade medida.

## Consequências
- Fronteiras precisam ser garantidas por convenção e por teste de importação (import-linter no CI, T011).
- Banco compartilhado: migrações coordenadas em um único histórico Alembic.
