# Três alvos (spec 011): `base` (sistema), `prod` (só dependências de execução) e `dev`
# (padrão, com as ferramentas de teste). O docker-compose.yml de desenvolvimento usa o último.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Bibliotecas de sistema que a wheel do rasterio (GDAL) usa e a imagem slim não traz (spec 008).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

FROM base AS prod
RUN python -c "import tomllib; d = tomllib.load(open('pyproject.toml', 'rb')); \
print('\n'.join(d['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt
COPY . .
RUN rm -rf app/tests && useradd --create-home --uid 1000 app && chown -R app:app /app \
    && mkdir -p /data/dem && chown app:app /data/dem
USER app
EXPOSE 8000
# Dois processos; o IP do cliente vem do X-Forwarded-For só de proxies confiáveis (FR-173).
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--no-server-header"]

FROM base AS dev
# Instala as dependências a partir do pyproject (camada em cache, sem copiar o código)
RUN python -c "import tomllib; d = tomllib.load(open('pyproject.toml', 'rb')); \
print('\n'.join(d['project']['dependencies'] + d['project']['optional-dependencies']['dev']))" \
    > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

COPY . .

# Usuário sem privilégios de root
RUN useradd --create-home --uid 1000 app && chown -R app:app /app \
    && mkdir -p /data/dem && chown app:app /data/dem
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
