# run_local.ps1

```powershell
# ============================================================
# run_local.ps1
# Ejecución local del backend TradingView Validation Layer
#
# Objetivo:
# - Activar entorno virtual
# - Cargar variables desde .env sin imprimir valores sensibles
# - Validar configuración mínima
# - Levantar FastAPI con uvicorn
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================"
Write-Host " TradingView Validation Layer - Local Run"
Write-Host "============================================================"
Write-Host ""

# ============================================================
# 1. Validar entorno virtual
# ============================================================

$activatePath = ".\.venv\Scripts\Activate.ps1"

if (-not (Test-Path $activatePath)) {
    Write-Host "[ERROR] No existe .venv."
    Write-Host "Ejecuta primero:"
    Write-Host "  .\setup_local.ps1"
    exit 1
}

Write-Host "[INFO] Activando entorno virtual..."
. $activatePath

# ============================================================
# 2. Validar archivo .env
# ============================================================

if (-not (Test-Path ".env")) {
    Write-Host "[ERROR] No existe archivo .env."
    Write-Host "Ejecuta primero:"
    Write-Host "  .\setup_local.ps1"
    Write-Host "Luego completa los valores necesarios en .env."
    exit 1
}

# ============================================================
# 3. Cargar variables desde .env sin mostrar valores
# ============================================================

Write-Host "[INFO] Cargando variables de entorno desde .env..."

Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()

    if ($line -eq "") {
        return
    }

    if ($line.StartsWith("#")) {
        return
    }

    if ($line -notmatch "=") {
        return
    }

    $parts = $line.Split("=", 2)
    $name = $parts[0].Trim()
    $value = $parts[1].Trim()

    if ($name -ne "") {
        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

Write-Host "[INFO] Variables cargadas correctamente."
Write-Host "[INFO] No se muestran valores sensibles por seguridad."

# ============================================================
# 4. Validar variables mínimas sin imprimir valores
# ============================================================

Write-Host ""
Write-Host "[INFO] Validando configuración mínima..."

$requiredVars = @(
    "WEBHOOK_SECRET",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY"
)

$optionalVars = @(
    "AWS_REGION",
    "SQS_QUEUE_URL",
    "S3_BUCKET_NAME",
    "S3_BASE_PREFIX",
    "TELEGRAM_ENABLED",
    "ENABLE_DATABRICKS_EXPORT",
    "DATABRICKS_EXPORT_TARGET"
)

$missingRequired = @()

foreach ($varName in $requiredVars) {
    $value = [System.Environment]::GetEnvironmentVariable($varName, "Process")

    if ([string]::IsNullOrWhiteSpace($value)) {
        Write-Host "[MISSING] $varName"
        $missingRequired += $varName
    }
    else {
        Write-Host "[OK] $varName configurada"
    }
}

foreach ($varName in $optionalVars) {
    $value = [System.Environment]::GetEnvironmentVariable($varName, "Process")

    if ([string]::IsNullOrWhiteSpace($value)) {
        Write-Host "[WARN] $varName no configurada"
    }
    else {
        Write-Host "[OK] $varName configurada"
    }
}

if ($missingRequired.Count -gt 0) {
    Write-Host ""
    Write-Host "[ERROR] Faltan variables obligatorias."
    Write-Host "Edita .env y completa las variables marcadas como MISSING."
    exit 1
}

# ============================================================
# 5. Test de importación
# ============================================================

Write-Host ""
Write-Host "[INFO] Probando importación de FastAPI app..."

python -c "from app.main import app; print('Import OK')"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Falló la importación de app.main."
    exit 1
}

# ============================================================
# 6. Ejecutar backend local
# ============================================================

$hostAddress = "127.0.0.1"
$port = "8000"

Write-Host ""
Write-Host "============================================================"
Write-Host " Iniciando backend local"
Write-Host "============================================================"
Write-Host ""
Write-Host "URL local:"
Write-Host "  http://$hostAddress`:$port"
Write-Host ""
Write-Host "Endpoints útiles:"
Write-Host "  GET  http://$hostAddress`:$port/"
Write-Host "  GET  http://$hostAddress`:$port/api/latest"
Write-Host "  GET  http://$hostAddress`:$port/api/validation/latest"
Write-Host "  GET  http://$hostAddress`:$port/api/health/binance"
Write-Host "  GET  http://$hostAddress`:$port/api/health/supabase"
Write-Host "  POST http://$hostAddress`:$port/api/webhook"
Write-Host ""
Write-Host "Presiona CTRL+C para detener."
Write-Host ""

python -m uvicorn app.main:app --host $hostAddress --port $port --reload
```