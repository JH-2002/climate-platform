# ADR-014 — Alertas oficiais (IDAP e INMET) e alertas do sistema por regras

- Status: **Aceita** (2026-11-24)
- Fase: 9 · Spec: [009](../../../specs/009-alerts/spec.md)

## Contexto
A Fase 9 precisa mostrar alertas oficiais e, separados deles, os alertas que o próprio sistema conclui (risco estimado, fontes paradas). A Constituição proíbe emitir alerta público (§1) e exige categorias distintas (§7.7). Em 2026-11-24 foram testadas:
- o feed CAP nacional da **IDAP** (Defesa Civil): público, Atom com CAP 1.2, ~16 MB, só ~12 h de histórico, um polígono por alerta;
- o **Alert-AS do INMET**: RSS público + uma mensagem CAP por aviso, com a lista de municípios (códigos IBGE) e `Update`/`Cancel`;
- o CGE da Prefeitura, que segue sem API (SOURCES.md §5).

## Decisão
1. **IDAP é a fonte dos alertas oficiais da Defesa Civil**, coletada a cada 10 min. A área vale pelo polígono, porque o `areaDesc` da Defesa Civil de SP traz o estado inteiro.
2. **INMET Alert-AS é a fonte dos avisos meteorológicos oficiais**, coletada a cada 30 min. A região vale pelo código IBGE (3550308), com o polígono como segunda opção.
3. **Limite do município pelas 32 subprefeituras do GeoSampa.** Isso dá a interseção real (não o retângulo) e permite dizer quais subprefeituras o alerta atinge.
4. **Texto oficial guardado e mostrado como veio**, com a mensagem CAP original em `raw_payloads`. Sem resumo automático.
5. **Alertas do sistema por regras puras e versionadas** (`alerts/rules.py`, versão `1`): risco por subprefeitura, fonte essencial parada e risco desatualizado. Eles abrem e fecham com histerese de duas avaliações e ficam numa tabela própria.
6. **Notificações só no navegador**, com permissão explícita e a aba aberta. Push, e-mail e SMS ficam para quando houver contas de usuário. O canal oficial (SMS 40199) é indicado na tela.
7. **XML com a biblioteca padrão**, recusando DOCTYPE e ENTITY antes do parse, sem dependência nova.

## Consequências
- O que a Defesa Civil manda à população passa a aparecer na plataforma minutos depois, com a área desenhada pela fonte.
- Se o coletor da IDAP parar por mais de 12 h, alertas se perdem. Por isso a fonte parada é ela mesma um alerta do sistema.
- O sistema não decide nada pela Defesa Civil: as regras internas só tratam da estimativa experimental e da saúde dos dados, com rótulo próprio.
- Os estados de atenção do CGE continuam fora até haver um acesso estável e permitido.

## Alternativas consideradas
- **Raspar o site do CGE**: rejeitada nesta fase. Seria scraping sem termos de uso verificados (Constituição §10).
- **`defusedxml`/`lxml`**: desnecessárias. Recusar DOCTYPE e ENTITY fecha os ataques conhecidos de XML, e a biblioteca padrão faz leitura em fluxo.
- **Push com service worker**: exige chaves VAPID, armazenamento de inscrições e um servidor de envio. Sem contas, não há a quem endereçar com segurança.
