# Spec 009 — Alertas

> Status: **Concluída** (2026-11-24) · Fase: 9 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md) · ADR: [ADR-014](../../docs/architecture/adr/ADR-014-official-alerts-and-rules.md)

## Contexto
A plataforma estima risco (Fase 5) e simula cenários (Fase 7), mas não mostra o que os órgãos oficiais estão dizendo. Quem abre a página num dia de temporal precisa ver, antes de tudo, **os alertas oficiais**, e só depois a estimativa experimental do sistema. A Constituição (§7.7) exige que alertas oficiais, avisos meteorológicos, risco estimado, qualidade de dados e simulação sejam categorias distintas, com rótulos distintos. E o sistema não emite alerta público (§1).

**Fontes testadas em 2026-11-24:**

| Fonte | O que é | Acesso | Observação |
|---|---|---|---|
| **IDAP — Defesa Civil** (MIDR) | Alertas que as Defesas Civis enviam à população (SMS, WhatsApp, Google Alertas Públicos, Defesa Civil Alerta) | Feed Atom com mensagens CAP 1.2, público, sem cadastro | ~16 MB, 161 alertas das ~12 h anteriores. 46 eram da Defesa Civil do Estado de SP, vários sobre a capital ("Chuva se espalhando pelas Zonas Oeste e Sul de São Paulo"). Cada alerta traz um **polígono**. O campo `areaDesc` vem como "SÃO PAULO/SP" para todo o estado, então a área vale pelo polígono. Só há `msgType` "Alert" |
| **INMET — Alert-AS** | Avisos meteorológicos (amarelo, laranja, vermelho) com até 5 dias de antecedência | RSS público + uma mensagem CAP 1.2 por aviso | 64 avisos no feed, 29 citando a capital (código IBGE 3550308 na lista de municípios). Usa `Alert`, `Update` e `Cancel` |
| **GeoSampa — `subprefeitura`** | 32 subprefeituras, com a região (Norte, Sul, Leste, Oeste, Centro) | WFS, como as camadas da Fase 5 | 2,3 MB. Dá o limite real do município e permite dizer quais subprefeituras um alerta atinge |
| CGE (Prefeitura) | Estados de atenção e alerta para alagamentos | Sem API pública (SOURCES.md §5) | **Fora desta fase**. A tela aponta para o site do CGE |

## Objetivo
Responder, nesta ordem:
1. Há alerta oficial da Defesa Civil ou aviso do INMET para a cidade agora (ou nas próximas horas)? Onde?
2. O que o sistema estima (risco experimental) e onde?
3. Os dados por trás disso estão em dia?

E avisar quem quiser, neste navegador, quando algo novo aparecer.

## Escopo
**Parte A — fontes oficiais, regras internas e API (backend)**
- Coleta do feed da IDAP (a cada 10 min) e do Alert-AS do INMET (a cada 30 min), guardando só os alertas que atingem a região, com a mensagem CAP original.
- Limite do município pelas subprefeituras do GeoSampa (sincronizado a cada 24 h).
- Ciclo de vida dos avisos: vigente, próximo, encerrado, cancelado ou substituído (`Update`/`Cancel` do INMET).
- Alertas do sistema por regras versionadas, com abertura, atualização e encerramento (sem duplicar):
  - risco estimado alto ou crítico por subprefeitura;
  - fonte essencial atrasada ou indisponível;
  - risco não recalculado há mais de 3 h.
- API de alertas e camada do mapa.

**Parte B — interface e notificações (frontend)**
- Página **Alertas** (`/alerts`) com as categorias separadas, mapa, detalhe e histórico de 7 dias.
- Faixa no topo de todas as páginas quando houver alerta oficial vigente para a cidade, e contador no menu.
- Cartão de alertas na Visão geral e no Clima, e camada no Mapa.
- Notificações do navegador (com permissão explícita), para alertas novos da cidade ou dos locais salvos.

**Fora do escopo**
- Emitir alerta público ou reenviar alerta oficial por SMS ou e-mail (Constituição §1).
- Notificação com o navegador fechado (push), e-mail ou SMS: exigem contas de usuário e envio pelo servidor (Fase 11 ou depois). A tela indica o canal oficial: SMS para 40199 com o CEP.
- Estados de atenção do CGE (sem API; melhoria registrada).
- Alertas do Cemaden, sem feed público confirmado para a capital (SOURCES.md §3).
- Regras definidas pelo usuário (limiares próprios): exigem contas.

## User stories
- **US-090** Como morador, quero saber na hora se a Defesa Civil emitiu alerta para a minha região e o que fazer.
- **US-091** Como gestor, quero ver, separados, os alertas oficiais e a estimativa do sistema, para não confundir um com o outro.
- **US-092** Como morador, quero ser avisado neste navegador quando surgir alerta para os meus locais salvos.
- **US-093** Como analista, quero o histórico dos alertas, com o texto original e a fonte, para comparar com as ocorrências.
- **US-094** Como mantenedor, quero saber quando uma fonte essencial parou, porque um alerta que não chega é pior que nenhum.

## Requisitos funcionais
### Parte A
- **FR-140 Feed da IDAP.**
  - Leitura em fluxo do feed Atom (até 60 MB), recusando DOCTYPE e entidades.
  - Guarda os alertas cujo polígono atinge o município, ou cujo código IBGE é o da região.
  - Cada alerta guardado tem a mensagem CAP original em `raw_payloads`.
  - Alerta que sai do feed continua guardado: o feed só mostra ~12 h.
- **FR-141 Avisos do INMET.**
  - Lê o RSS e busca a mensagem CAP de cada aviso ainda não guardado.
  - Guarda os avisos cuja lista de municípios tem o código IBGE da região ou cujo polígono atinge o município.
  - `Update` encerra o aviso anterior como substituído e passa a valer no lugar dele.
  - `Cancel` encerra o aviso referenciado como cancelado e não aparece como aviso.
  - O encerramento vale em qualquer ordem de chegada (o `Cancel` pode chegar antes do aviso).
- **FR-142 Limite do município.**
  - As 32 subprefeituras do GeoSampa são sincronizadas a cada 24 h, no padrão da Fase 5.
  - O limite do município é a união das subprefeituras. Sem elas, vale o retângulo da região, e o alerta fica marcado como "área aproximada".
  - Para cada alerta oficial, o sistema guarda as subprefeituras atingidas e a fração da área do município coberta.
- **FR-143 Estado de um alerta oficial** (calculado na leitura):
  - **Próximo**: começa no futuro;
  - **Vigente**: começou e não terminou;
  - **Encerrado**: passou do fim;
  - **Cancelado** ou **Substituído**: encerrado pela fonte.
- **FR-144 Alertas do sistema.** Regras versionadas, avaliadas após cada cálculo de risco, após cada coleta de alertas e a cada 10 min:
  - `risk-subprefecture`: uma subprefeitura com setor em alto ou crítico na estimativa mais recente. O nível é o maior entre os setores, e a mensagem diz quantos setores.
  - `source-unavailable`: previsão da Open-Meteo, IDAP ou INMET com frescor STALE ou UNAVAILABLE.
  - `risk-stale`: nenhum cálculo de risco com sucesso há mais de 3 h.
  
  Abrir, atualizar e encerrar:
  - um alerta do sistema fica aberto enquanto a condição vale;
  - é atualizado quando o nível ou a contagem mudam;
  - é encerrado depois de **duas avaliações seguidas** sem a condição.
  
  Nunca há dois alertas abertos da mesma regra para o mesmo escopo.
- **FR-145 API.**
  - `GET /alerts/active`: alertas oficiais vigentes e próximos (até 48 h), alertas do sistema abertos, contagens e o frescor das fontes de alerta.
  - `GET /alerts?categoria=&desde=&ate=&pagina=`: histórico (até 90 dias por consulta).
  - `GET /alerts/official/{id}`: detalhe com texto completo, instrução, fonte e área.
  - `GET /alerts/at?lat=&lon=`: alertas oficiais vigentes ou próximos que cobrem um ponto.
  - `GET /alerts/rules`: regras, limiares, versão e estado.
  - `GET /map/layers/alerts`: polígonos dos alertas oficiais vigentes e próximos, recortados à região.

### Parte B
- **FR-146 Página `/alerts`.**
  - Ordem: alertas oficiais da Defesa Civil → avisos do INMET → estimativa do sistema → qualidade dos dados.
  - Cada cartão traz: fonte, severidade com texto e ícone, vigência no horário de Brasília, subprefeituras atingidas e instrução da fonte.
  - Mapa com os polígonos, histórico de 7 dias e estados vazio, erro e fonte atrasada.
- **FR-147 Faixa e contador.** Com alerta oficial vigente para a cidade, uma faixa no topo de todas as páginas diz a fonte, a severidade e o título, com link para o detalhe. O menu mostra o número de alertas oficiais vigentes.
- **FR-148 Outras telas.** Cartão "Alertas agora" na Visão geral e no Clima. Camada "Alertas oficiais" no Mapa, desligada por padrão.
- **FR-149 Notificações neste navegador.**
  - Ligadas só por escolha do usuário, que dá a permissão do navegador. Desligá-las é sempre possível.
  - Com uma aba aberta, a página consulta os alertas a cada 2 min.
  - Avisa uma única vez cada alerta novo: oficial para a cidade (ou só para os locais salvos, se o usuário escolher) e do sistema em nível crítico.
  - A escolha e os alertas já avisados ficam no navegador.

## Requisitos não funcionais
- **NFR-140** O parse da IDAP e do INMET fica em adapters puros (`integrations/idap/`, `integrations/inmet/warnings.py`), testados com mensagens reais gravadas (recortadas; até 200 KB no total). O XML recusa DOCTYPE e entidades.
- **NFR-141** A leitura do feed da IDAP usa pouca memória: processa alerta por alerta e descarta os que não atingem a região antes de montar a geometria.
- **NFR-142** `GET /alerts/active` responde em menos de 200 ms. A camada do mapa manda polígonos simplificados, com no máximo 1 MB.
- **NFR-143** As regras dos alertas do sistema ficam num módulo puro (`app/alerts/rules.py`), testado sem banco. Os limiares são configuráveis.
- **NFR-144** Acessibilidade: a faixa usa `role="alert"` só quando aparece um alerta novo (não a cada consulta). Severidade sempre com texto, e a lista acompanha o mapa.

## Regras de negócio
- **BR-140 Categorias e rótulos** (Constituição §7.7):
  - "Alerta oficial — Defesa Civil";
  - "Aviso meteorológico oficial — INMET";
  - "Estimativa do sistema — não é alerta oficial";
  - "Qualidade dos dados".
  
  Nunca se misturam numa mesma lista sem o rótulo.
- **BR-141 Texto oficial intocado.** Título, descrição e instrução aparecem como a fonte escreveu, com link para a fonte. O sistema não resume nem reescreve o alerta oficial.
- **BR-142 Severidade.**
  - CAP (Menor, Moderada, Severa, Extrema).
  - Para o INMET, também a cor e o nome oficiais: amarelo "Perigo potencial", laranja "Perigo", vermelho "Grande perigo".
  - Os alertas do sistema usam as categorias do motor de risco (alto, crítico), nunca as cores oficiais de severidade.
- **BR-143 Simulação não gera alerta.** Resultados do Laboratório (Fase 7) nunca abrem alerta do sistema nem disparam notificação.
- **BR-144 Fonte parada.** Se a IDAP ou o INMET estiverem atrasados ou indisponíveis, a página diz isso no lugar de "nenhum alerta". "Nenhum alerta" só aparece com as fontes em dia.
- **BR-145 Atribuição.** "Fonte: Defesa Civil (IDAP/MIDR)"; "Fonte: INMET — Alert-AS"; limite das subprefeituras: GeoSampa, Prefeitura de São Paulo.

## Critérios de aceite
- **AC-140** *Given* o feed gravado da IDAP com um alerta sobre as Zonas Oeste e Sul e outro sobre Sorocaba, *When* a coleta roda, *Then* só o primeiro é guardado, com as subprefeituras da Zona Oeste/Sul entre as atingidas.
- **AC-141** *Given* um aviso do INMET e, depois, um `Cancel` que o referencia, *When* as duas coletas rodam, *Then* o aviso aparece como cancelado e não há aviso novo.
- **AC-142** *Given* a mesma coleta repetida, *Then* nenhum alerta é duplicado e os contadores da execução mostram 0 inseridos.
- **AC-143** *Given* uma subprefeitura com setores em alto, *When* as regras rodam duas vezes, *Then* há um único alerta do sistema aberto. *Given* que os setores voltam a baixo, *Then* ele só fecha na segunda avaliação seguida.
- **AC-144** *Given* a IDAP sem coleta com sucesso há mais de 3 ciclos, *When* abro `/alerts`, *Then* vejo "fonte atrasada" e não "nenhum alerta", e há um alerta de qualidade dos dados aberto.
- **AC-145** *Given* um alerta oficial vigente, *When* abro qualquer página, *Then* vejo a faixa com a fonte e a severidade, e o leitor de tela a anuncia uma vez.
- **AC-146** *Given* notificações ligadas, *When* surge um alerta novo, *Then* o navegador avisa uma vez. *Given* que recarrego a página, *Then* não avisa de novo.
- **AC-147** *Given* uma simulação com setores em crítico, *Then* nenhum alerta do sistema é aberto.

## Dependências
- Specs 002 (pipeline de ingestão e frescor), 005 (motor de risco e setores) e 003 (locais salvos no navegador).
- Nenhuma biblioteca nova: o XML é lido com a biblioteca padrão, com DOCTYPE e entidades recusados.

## Riscos e limitações
- **Feed da IDAP guarda só ~12 h.** Com o coletor parado por mais que isso, alertas se perdem. O alerta de qualidade dos dados (FR-144) existe para isso.
- **Área dos alertas da Defesa Civil.** O polígono é desenhado à mão pelo operador e às vezes é grosseiro. A tela mostra a área como a fonte enviou.
- **Avisos do INMET são regionais.** Um aviso pode cobrir meio país. A tela diz que a área é a da mesorregião e não aponta bairros.
- **Notificação depende da aba aberta.** Sem push, nada chega com o navegador fechado. A tela diz isso e indica o SMS 40199 da Defesa Civil.
- **CGE fora.** A fonte mais específica para alagamentos na capital não tem API. A tela aponta para o site.
