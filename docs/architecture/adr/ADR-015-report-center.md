# ADR-015 — Relatórios com PDF próprio e arquivos no banco

- Status: **Aceita** (2026-11-25)
- Fase: 10 · Spec: [010](../../../specs/010-report-center/spec.md)

## Contexto
A Fase 10 gera relatórios em PDF, CSV e JSON, em segundo plano. As opções para o PDF eram uma biblioteca (ReportLab, WeasyPrint, wkhtmltopdf) ou um escritor próprio. Para o armazenamento, um volume novo no Docker ou o banco.

## Decisão
1. **Escritor de PDF próprio e puro**, com as fontes padrão do PDF (Helvetica e Helvetica-Bold), codificação WinAnsi e as larguras das métricas AFM da Adobe (distribuídas livremente com as fontes padrão). Faz texto com quebra de linha, tabelas paginadas, gráfico de barras e rodapé.
2. **Um conteúdo neutro e três escritores.** O mesmo `Report` vira PDF, CSV ou JSON, então os formatos nunca divergem.
3. **Arquivos no banco (`bytea`)**, com teto de 20 MB e retenção de 7 dias.

## Motivos
- Nenhuma dependência nova: a imagem não precisa ser reconstruída, e o projeto já faz o mesmo com o PNG do relevo (ADR-013).
- WeasyPrint e wkhtmltopdf exigem bibliotecas do sistema (Pango, Qt) e aumentam muito a imagem. ReportLab resolveria, mas o relatório só precisa de texto, tabelas e barras.
- Um volume novo exigiria mudar o `docker-compose.yml` e recriar os contêineres. No banco, os arquivos entram no mesmo backup e são apagados com o pedido.

## Consequências
- O PDF não embute fontes nem imagens: é sóbrio. Caracteres fora do WinAnsi (emoji, ideogramas) viram `?`; os textos das fontes oficiais usadas são português.
- Se um dia o relatório precisar de mapa em imagem ou layout rico, a troca por uma biblioteca fica restrita a `reports/pdf.py`.
