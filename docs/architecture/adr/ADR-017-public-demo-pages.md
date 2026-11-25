# ADR-017 — Vitrine pública estática no GitHub Pages, gravada pelo Actions

- Status: **Aceita** (2026-11-25)
- Fase: 12 · Spec: [012](../../../specs/012-public-demo/spec.md)

## Contexto
A pilha de produção (ADR-016) precisa de um servidor ligado o tempo todo, e o usuário não tem
hospedagem agora. O GitHub Pages é gratuito para repositórios públicos, mas só serve arquivos
estáticos. O GitHub Actions, também gratuito em repositório público, pode subir a plataforma
inteira por alguns minutos (PostGIS e Redis como serviços).

## Decisão
Publicar uma vitrine estática no Pages. Um workflow agendado (a cada 6 h) sobe banco, Redis e a
API, roda as coletas reais, percorre a interface com o Playwright gravando as respostas GET da
API, monta o frontend com `output: "export"` num modo demonstração que lê essas respostas de
arquivos e publica. Simulações só dos cenários prontos (gravados); relatórios desligados.

## Alternativas consideradas
- **Hospedagem grátis com servidor** (Oracle Always Free): plataforma completa, mas a cota foi
  reduzida em 2026, a capacidade é difícil de conseguir e as máquinas são ARM. Continua como
  caminho para a publicação completa.
- **Gravar uma vez na máquina local e versionar os arquivos:** dados ficariam velhos e o
  repositório cresceria a cada atualização.
- **Lista fixa de rotas para gravar:** quebra a cada mudança na interface; gravar o que a
  interface pede acompanha o frontend sozinho.

## Consequências
- Link público sem custo, com dados reais de até 6 h atrás e o mesmo código da plataforma.
- Interações que pedem consultas não gravadas mostram "Indisponível na demonstração".
- Dependemos do agendamento do Actions (pode atrasar em horários de pico) e de as fontes
  externas aceitarem os executores do GitHub.
