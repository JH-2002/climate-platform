# Validação da pilha de produção na própria máquina (spec 011: T186, T187).
# Uso, na pasta do projeto:
#   powershell -ExecutionPolicy Bypass -File scripts\validar-producao.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\validar-producao.ps1 -Parar   # derruba a pilha
# Sobe docker-compose.prod.yml em https://localhost:8443 (sem tocar na pilha de desenvolvimento),
# confere saúde e cabeçalhos, faz um backup, restaura num banco novo e compara as contagens.
# Tudo vai para validacao-producao.log, na raiz do projeto.
param([switch]$Parar)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$Log = Join-Path (Get-Location) "validacao-producao.log"
$Compose = @("compose", "-f", "docker-compose.prod.yml", "--env-file", ".env.prod")
$Base = "https://localhost:8443"

function Registrar([string]$texto) {
  $linha = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $texto
  Write-Host $linha
  Add-Content -Path $Log -Value $linha -Encoding UTF8
}
function Docker([string[]]$argumentos) {
  $saida = & docker @Compose @argumentos 2>&1 | Out-String
  Add-Content -Path $Log -Value $saida -Encoding UTF8
  return $saida
}
function Senha {
  $bytes = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  return ([Convert]::ToBase64String($bytes) -replace "[^A-Za-z0-9]", "").Substring(0, 32)
}

if ($Parar) {
  Docker @("down") | Out-Null
  Write-Host "Pilha de produção parada (os volumes continuam)."
  exit 0
}

Set-Content -Path $Log -Value "Validação da produção - $(Get-Date -Format s)" -Encoding UTF8

if (-not (Test-Path ".env.prod")) {
  $modelo = Get-Content ".env.prod.example" -Encoding UTF8
  $modelo = $modelo `
    -replace "^DOMAIN=.*", "DOMAIN=localhost" `
    -replace "^CADDY_HTTP_PORT=.*", "CADDY_HTTP_PORT=8080" `
    -replace "^CADDY_HTTPS_PORT=.*", "CADDY_HTTPS_PORT=8443" `
    -replace "^POSTGRES_PASSWORD=.*", "POSTGRES_PASSWORD=$(Senha)" `
    -replace "^REDIS_PASSWORD=.*", "REDIS_PASSWORD=$(Senha)" `
    -replace "^BACKUP_ON_START=.*", "BACKUP_ON_START=1"
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  [IO.File]::WriteAllLines((Join-Path (Get-Location) ".env.prod"), $modelo, $utf8)
  Registrar ".env.prod criado para teste local (localhost:8443, senhas aleatórias)."
} else {
  Registrar ".env.prod já existe: usando o atual."
}

Registrar "Construindo e subindo a pilha (a primeira vez leva alguns minutos)..."
Docker @("up", "-d", "--build") | Out-Null

Registrar "Esperando a API ficar pronta (até 10 min)..."
$pronta = $false
for ($i = 0; $i -lt 60; $i++) {
  $codigo = & curl.exe -sk -o NUL -w "%{http_code}" "$Base/api/v1/health/ready"
  if ($codigo -eq "200") { $pronta = $true; break }
  Start-Sleep -Seconds 10
}
Registrar "Prontidão: $(if ($pronta) { 'OK' } else { 'FALHOU' })"
Docker @("ps", "--format", "table {{.Service}}\t{{.Status}}") | Out-Null
if (-not $pronta) {
  Registrar "Últimas linhas dos serviços:"
  Docker @("logs", "--tail=40", "migrate", "api", "frontend", "caddy") | Out-Null
  exit 1
}

Registrar "Cabeçalhos do site:"
Add-Content -Path $Log -Value (& curl.exe -skI "$Base/" | Out-String) -Encoding UTF8
Registrar "Cabeçalhos da API:"
Add-Content -Path $Log -Value (& curl.exe -skI "$Base/api/v1/health" | Out-String) -Encoding UTF8
Registrar "Redirecionamento de http para https:"
Add-Content -Path $Log -Value (& curl.exe -sI "http://localhost:8080/" | Out-String) -Encoding UTF8
Registrar "Portas publicadas (só o Caddy deve aparecer):"
Docker @("ps", "--format", "table {{.Service}}\t{{.Ports}}") | Out-Null

Registrar "Esperando a primeira carga dos setores de risco (até 10 min)..."
for ($i = 0; $i -lt 60; $i++) {
  $n = (Docker @("exec", "-T", "backup", "psql", "-tAc", "SELECT count(*) FROM hydro_risk_sectors")).Trim()
  if ($n -match "^\d+$" -and [int]$n -gt 0) { break }
  Start-Sleep -Seconds 10
}
Registrar "Setores carregados: $n"

Registrar "Backup manual:"
$arquivo = "climate_validacao_$(Get-Date -Format yyyy-MM-dd_HHmm).dump"
Docker @("exec", "-T", "backup", "pg_dump", "--format=custom", "--no-owner", "--file=/backups/$arquivo") | Out-Null
Docker @("exec", "-T", "backup", "ls", "-l", "/backups") | Out-Null

Registrar "Restaurando $arquivo no banco climate_restore:"
$restaurar = "set -e; dropdb --if-exists climate_restore; createdb climate_restore; " +
  "psql -d climate_restore -q -c 'CREATE EXTENSION IF NOT EXISTS postgis'; " +
  "pg_restore --no-owner --dbname=climate_restore /backups/$arquivo && echo RESTAURADO"
Docker @("exec", "-T", "backup", "bash", "-c", $restaurar) | Out-Null

Registrar "Contagens (restaurado x em uso):"
foreach ($tabela in @("data_sources", "hydro_risk_sectors", "subprefectures", "weather_forecasts", "risk_assessments", "official_alerts")) {
  $r = (Docker @("exec", "-T", "backup", "psql", "-d", "climate_restore", "-tAc", "SELECT count(*) FROM $tabela")).Trim()
  $v = (Docker @("exec", "-T", "backup", "psql", "-tAc", "SELECT count(*) FROM $tabela")).Trim()
  Registrar ("  {0,-20} restaurado: {1,-8} em uso: {2}" -f $tabela, $r, $v)
}

Registrar "Log do serviço de backup:"
Docker @("logs", "--tail=10", "backup") | Out-Null
Registrar "Uso de memória:"
Add-Content -Path $Log -Value (& docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | Out-String) -Encoding UTF8

Registrar "Concluído. A pilha continua no ar em $Base (o navegador vai pedir para aceitar o certificado local)."
Registrar "Para parar: powershell -ExecutionPolicy Bypass -File scripts\validar-producao.ps1 -Parar"
