# Spec 008 — Geointeligência 3D

> Status: **Aprovada** (2026-11-20) · Fase: 8 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md) · ADR: [ADR-013](../../docs/architecture/adr/ADR-013-terrain-and-hydrography.md)

## Contexto
O mapa da Fase 4 já mostra relevo em 3D, mas o relevo é **só visual** (Terrain Tiles, ADR-009). O motor de risco da Fase 5 não sabe em que **bacia** um setor está, nem se ele fica num **fundo de vale** ou numa encosta. O roadmap pede para esta fase: terreno do Copernicus DEM, camadas 3D e alternativa em 2D.

**Fontes testadas em 2026-11-20:**

| Fonte | O que é | Acesso | Observação |
|---|---|---|---|
| **Copernicus DEM GLO-30** (ESA) | Elevação em grade de ~30 m | HTTPS público no bucket da AWS, sem conta; 2 blocos de 1° cobrem a cidade (S24 W047 com 42 MB e S25 W047 com 4,8 MB, quase todo mar) | Modelo de **superfície**: inclui prédios e árvores. Bom para a escala de bairro e de bacia, não para a de rua (Constituição §13) |
| **GeoSampa — `bacia_hidrografica`** | 269 bacias e sub-bacias, com a bacia principal (Tietê, Pinheiros, Tamanduateí…) | WFS, como as camadas da Fase 5 | Atualizada em 08/2026 |
| **GeoSampa — `drenagem`** | 28.366 trechos de rios e córregos, inclusive canalizados e subterrâneos | WFS | O tipo do trecho (aberto, canalizado, subterrâneo) vem na fonte |
| **GeoSampa — `reservatorio_amortecimento`** | 72 piscinões, com volume, bacia e tipo | WFS | Volume ausente em parte deles |
| GeoSampa — LiDAR MDT/MDS 2020 | Terreno da Prefeitura, 10 pontos/m² | Nuvens de pontos (LAZ) baixadas folha a folha no portal (5.401 folhas 1:1000) | **Fora desta fase**: não dá para automatizar para a cidade inteira. Pode servir depois para o detalhe de um local |

## Objetivo
Responder, com dados rastreáveis:
- Em que bacia fica cada setor de risco, e quais bacias concentram setores, ocorrências e piscinões?
- Um setor está num fundo de vale ou numa encosta, e perto de qual córrego?
- Como é o relevo entre dois pontos (perfil)?
- Como a bacia se parece em 3D, com os setores, a drenagem e os piscinões?

Tudo com alternativa em 2D e sem transformar relevo em previsão de inundação.

## Escopo
Dividido em duas partes, entregues e validadas em sequência.

**Parte A — relevo e hidrografia (dados e 2D)**
- Ingestão do Copernicus DEM: download único dos 2 blocos, conferência de tamanho e ETag, recorte da região e gravação num volume.
- Ingestão das 3 camadas do GeoSampa (bacias, drenagem, piscinões), no mesmo padrão da Fase 5.
- Métricas de terreno por setor de risco (tipo `DERIVED`):
  - elevação mediana e mínima;
  - declividade média;
  - **elevação relativa** (mediana do setor menos a mediana do entorno de 1 km): negativa indica fundo de vale;
  - distância até o curso d'água mais próximo e o tipo dele;
  - bacia.
- Métricas por bacia:
  - área e faixa de elevação;
  - setores por grau e por categoria de risco atual;
  - ocorrências dos últimos 12 meses;
  - piscinões e volume somado.
- Perfil de elevação entre pontos: amostras a cada ~30 m, até 20 km, marcando os cursos d'água e os setores cruzados.
- Página **Geointeligência 3D** (`/geo-3d`) no mapa MapLibre:
  - camadas de bacias, drenagem e piscinões sobre o relevo;
  - ranking e ficha de cada bacia;
  - perfil traçado com dois cliques e mostrado em gráfico;
  - a ficha do setor na página de Risco passa a mostrar o terreno.

**Parte B — bloco 3D da bacia** *(revisado em 2026-11-24: MapLibre sobre o relevo do Copernicus, sem Three.js; ver ADR-013)*
- Para a bacia escolhida, o terreno 3D do MapLibre alimentado pelo **próprio Copernicus**, servido pelo backend em blocos de relevo. O 3D usa o mesmo relevo dos cálculos. O exagero vertical é ajustável.
- Por cima do terreno: drenagem, piscinões e setores coloridos pela estimativa real **ou por uma simulação da Fase 7** (escolhida pelo link da simulação). Fora da bacia, o mapa fica esmaecido.
- Controles de órbita por mouse, toque e teclado (os do MapLibre), reinício da vista e exportação de imagem.
- Alternativa em 2D: relevo sombreado da bacia gerado no servidor, com os mesmos setores, drenagem e piscinões, e tabela. Aparece quando não há WebGL ou o usuário prefere reduzir movimento.

**Fora do escopo**
- **Mancha de inundação por cota** ("encher" o relevo até um nível): num modelo de superfície de 30 m, sem a rede de drenagem real, seria uma inundação inventada.
- Direção de fluxo e acumulação calculadas do DEM: os prédios do modelo de superfície desviam o escoamento. A drenagem vem da Prefeitura.
- Mudar o motor de risco: as métricas de terreno ficam disponíveis para calibrar o motor depois, com ocorrências de vários anos.
- LiDAR da Prefeitura (ver Contexto).
- Terreno do mapa base: o relevo visual continua o do ADR-009. O Copernicus serve para os cálculos.

## User stories
- **US-080** Como gestor, quero saber quais bacias concentram setores de risco, ocorrências e piscinões, para priorizar ações por bacia.
- **US-081** Como analista, quero saber se um setor está em fundo de vale e perto de qual córrego.
- **US-082** Como pesquisador, quero traçar um perfil do relevo entre dois pontos e ver os córregos no caminho.
- **US-083** Como morador, quero ver a minha região em 3D, com a drenagem e os setores, entendendo o que cada cor significa.
- **US-084** Como analista, quero ver uma simulação da Fase 7 sobre o relevo da bacia.

## Requisitos funcionais
### Parte A
- **FR-120 DEM.**
  - Uma tarefa baixa os blocos do Copernicus GLO-30 que cobrem a região, confere tamanho e ETag, recorta a região e grava o recorte com os metadados de origem.
  - O download acontece só na primeira vez, ou quando o arquivo some ou fica corrompido.
  - A execução fica em `ingestion_runs`, como as demais fontes.
- **FR-121 Hidrografia.**
  - As 3 camadas do GeoSampa são sincronizadas a cada 30 dias, no padrão da Fase 5: payload bruto, normalização, desativação do que sumiu e falha registrada.
  - Os trechos de drenagem guardam o tipo do trecho (aberto, canalizado, subterrâneo).
- **FR-122 Terreno por setor.** Depois do DEM e a cada sincronização de setores ou de drenagem, o sistema calcula e grava, para cada setor ativo:
  - elevação mediana e mínima;
  - declividade média;
  - elevação relativa ao entorno de 1 km;
  - curso d'água mais próximo (distância, tipo e nome, se houver);
  - bacia.
  
  Um setor que fica em mais de uma bacia é atribuído à de maior área de interseção.
- **FR-123 Bacias.**
  - `GET /geo/basins`: lista com as métricas e ordenação.
  - `GET /geo/basins/{id}`: ficha com setores, piscinões, ocorrências e risco atual.
  - `GET /map/layers/basins`, `/map/layers/drainage` (com recorte por área e simplificação conforme o zoom) e `/map/layers/reservoirs`: camadas do mapa.
- **FR-124 Perfil.**
  - `GET /geo/profile?pontos=lon,lat;lon,lat…`: de 2 a 10 pontos, até 20 km no total.
  - Devolve as amostras (distância e elevação), os cursos d'água e os setores cruzados, com a posição de cada um no perfil, e o ganho e a perda de elevação.
- **FR-125 Elevação de um ponto.** `GET /geo/elevation?lat=&lon=`: elevação, declividade, elevação relativa, bacia e curso d'água mais próximo.
- **FR-126 Página `/geo-3d`.**
  - Mapa 3D com relevo, bacias (cor pelo número de setores em alto ou crítico agora), drenagem e piscinões.
  - Ranking de bacias e ficha da bacia escolhida.
  - Perfil: dois ou mais cliques no mapa e, em seguida, o gráfico.
  - Estado na URL.
- **FR-127 Terreno na ficha do setor.** A explicação do setor (página de Risco e Laboratório) ganha a seção "Terreno": elevação, elevação relativa, bacia e córrego mais próximo. Ela é informativa e não muda a categoria (ver BR-121).

### Parte B
- **FR-128 Bloco 3D.**
  - `GET /geo/terrain/{z}/{x}/{y}.png`: blocos de relevo no formato "terrarium" do MapLibre, gerados do recorte do Copernicus (zoom 6 a 14, com cache).
  - `GET /geo/basins/{id}/block`: limites, faixa de elevação e setores da bacia.
  - O frontend mostra a bacia no terreno 3D do MapLibre, com exagero vertical de 1× a 5×.
- **FR-129 Camadas sobre o bloco.** Drenagem, piscinões e setores, coloridos pela estimativa real mais recente ou por uma simulação (`?simulacao=<id>`), com a faixa de simulação (BR-100 da spec 007) quando for o caso.
- **FR-130 Controles e exportação.**
  - Órbita, zoom e reinício da vista por mouse, toque e teclado.
  - Exportação PNG, com título, legenda e fontes na própria imagem.
- **FR-131 Alternativa em 2D.** `GET /geo/basins/{id}/relief.png`: relevo sombreado da bacia, com os mesmos setores, drenagem e piscinões, mais a tabela dos setores. Aparece quando não há WebGL, quando o usuário prefere reduzir movimento ou quando escolhe a versão 2D.

## Requisitos não funcionais
- **NFR-120** Os cálculos de terreno ficam num módulo puro (`app/geo/`), com rasterio e numpy só na camada que lê o arquivo. O módulo é testado com uma grade sintética pequena e um recorte real gravado como fixture, de no máximo 200 KB.
- **NFR-121** O perfil responde em menos de 500 ms. A grade da bacia responde em menos de 1 s e pode ir para cache.
- **NFR-122** O bloco 3D roda a 30 quadros por segundo num notebook comum. O MapLibre da vista 3D só é carregado nela. Os blocos de relevo ficam em cache no servidor e no navegador (24 h).
- **NFR-123** A camada de drenagem não manda os 28 mil trechos de uma vez: recorte por área visível e simplificação conforme o zoom, com no máximo 5 MB por resposta.
- **NFR-124** Acessibilidade: o perfil tem tabela e descrição, e o bloco 3D tem alternativa em 2D e controles por teclado.

## Regras de negócio
- **BR-120 Limites do DEM, ditos na tela.**
  - É um modelo de **superfície** com 30 m de resolução: prédios e árvores entram na elevação.
  - Serve para comparar bairros e bacias, não ruas.
  - Cada número de terreno traz a fonte e a resolução.
- **BR-121 Terreno é contexto, não risco.** As métricas de terreno não mudam a categoria de risco nesta fase. Usá-las no motor exige calibração com ocorrências (melhoria registrada), com nova versão do motor.
- **BR-122 Nada de inundação inventada.** Nenhuma tela pinta área "inundável" a partir do relevo. As únicas manchas de inundação mostradas são as oficiais do GeoSampa (Fase 5).
- **BR-123 Atribuição.**
  - Copernicus: "Produced using Copernicus DEM GLO-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved". O texto exato é conferido na licença durante a T120.
  - GeoSampa: Prefeitura de São Paulo.

## Critérios de aceite
- **AC-120** *Given* os blocos baixados, *When* a tarefa roda de novo, *Then* não baixa outra vez e o recorte cobre toda a região, sem células vazias dentro do município.
- **AC-121** *Given* um setor sabidamente em várzea (ex.: perto do Rio Tietê), *When* consulto o terreno, *Then* a elevação relativa é negativa e o curso d'água mais próximo está a menos de 500 m. *Given* um setor em encosta, *Then* a declividade é maior que a média dos setores.
- **AC-122** *Given* o perfil entre dois pontos dos dois lados do Tietê, *When* peço, *Then* o ponto mais baixo fica perto do rio, que aparece marcado no perfil.
- **AC-123** *Given* a lista de bacias, *Then* a soma dos setores atribuídos é igual ao total de setores ativos, e cada setor está em exatamente uma bacia ou em "fora das bacias mapeadas".
- **AC-124** *Given* uma bacia, *When* abro o bloco 3D, *Then* vejo o relevo, a drenagem e os setores com legenda. *Given* `?simulacao=<id>`, *Then* as cores são as da simulação e a faixa de simulação aparece.
- **AC-125** *Given* um navegador sem WebGL, *When* abro a vista 3D, *Then* vejo a alternativa em 2D com as mesmas informações.
- **AC-126** *Given* qualquer tela de terreno, *Then* aparecem a fonte, a resolução e o aviso de modelo de superfície.

## Dependências
- Specs 004 (mapa), 005 (setores e GeoSampa) e 007 (simulações, Parte B).
- Bibliotecas novas: `rasterio` e `numpy` (backend). Nenhuma no frontend: o bloco 3D usa o MapLibre já presente.

## Riscos e limitações
- **Modelo de superfície de 30 m.** Em área densa, um setor pequeno pode ter a elevação de telhados. A elevação relativa usa medianas para reduzir esse efeito, mas não o elimina.
- **Setores pequenos.** Muitos setores têm menos de 1 ha, ou seja, poucas células de 30 m. Setores com menos de 4 células são marcados como "pouca amostra".
- **Download de ~47 MB na primeira vez.** Se a rede falhar, a tarefa tenta de novo no ciclo seguinte. As outras funções da plataforma não dependem disso.
- **Licença do Copernicus.** Uso livre com atribuição. Ela fica registrada no SOURCES e aparece na tela.
