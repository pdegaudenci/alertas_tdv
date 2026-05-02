# setup_local.ps1

```powershell
# ============================================================
# setup_local.ps1
# Preparación local del backend TradingView Validation Layer
#
# Objetivo:
# - Crear entorno virtual local
# - Instalar dependencias
# - Crear .env desde .env.example si no existe
# - No imprimir secretos ni valores sensibles
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================"
Write-Host " TradingView Validation Layer - Local Setup"
Write-Host "============================================================"
Write-Host ""

# ============================================================
# 1. Validar ubicación
# ============================================================

if (-not (Test-Path "requirements.txt")) {
    Write-Host "[ERROR] No se encontró requirements.txt en la carpeta actual."
    Write-Host "Ejecuta este script desde la raíz del backend."
    exit 1
}

# ============================================================
# 2. Crear entorno virtual
# ============================================================

if (-not (Test-Path ".venv")) {
    Write-Host "[INFO] Creando entorno virtual .venv..."
    python -m venv .venv
}
else {
    Write-Host "[INFO] Entorno virtual .venv ya existe."
}

# ============================================================
# 3. Activar entorno virtual
# ============================================================

$activatePath = ".\.venv\Scripts\Activate.ps1"

if (-not (Test-Path $activatePath)) {
    Write-Host "[ERROR] No se encontró el script de activación del entorno virtual."
    exit 1
}

Write-Host "[INFO] Activando entorno virtual..."
. $activatePath

# ============================================================
# 4. Actualizar pip
# ============================================================

Write-Host "[INFO] Actualizando pip..."
python -m pip install --upgrade pip

# ============================================================
# 5. Instalar dependencias
# ============================================================

Write-Host "[INFO] Instalando dependencias desde requirements.txt..."
python -m pip install -r requirements.txt

# ============================================================
# 6. Crear .env.example si no existe
# ============================================================

if (-not (Test-Path ".env.example")) {
    Write-Host "[INFO] Creando .env.example sin valores sensibles..."

@"
# ============================================================
# TradingView Validation Layer - Local Environment Example
# NO incluir valores reales en este archivo si se sube a GitHub.
# Copiar como .env y completar localmente.
# ============================================================

# ------------------------------------------------------------
# Backend / Webhook Security
# ------------------------------------------------------------
WEBHOOK_SECRET=

# ------------------------------------------------------------
# Validation
# ------------------------------------------------------------
VALIDATION_THRESHOLD=0.62
MIN_SCORE_THRESHOLD=55
REQUEST_TIMEOUT_SEC=8.0
VALIDATION_MODEL_VERSION=rules_v1

# ------------------------------------------------------------
# Supabase
# ------------------------------------------------------------
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_ENABLED=true

# ------------------------------------------------------------
# Telegram
# ------------------------------------------------------------
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ------------------------------------------------------------
# Machine Learning optional
# ------------------------------------------------------------
ML_MODEL_PATH=
ML_FEATURES_JSON=

# ------------------------------------------------------------
# CORS
# ------------------------------------------------------------
ALLOWED_ORIGINS=*

# ------------------------------------------------------------
# AWS general
# ------------------------------------------------------------
AWS_REGION=eu-west-1

# ------------------------------------------------------------
# AWS SQS
# ------------------------------------------------------------
SQS_ENABLED=true
SQS_QUEUE_URL=
SQS_DLQ_URL=

# ------------------------------------------------------------
# AWS S3 / Databricks Lakehouse Export
# ------------------------------------------------------------
ENABLE_DATABRICKS_EXPORT=true
DATABRICKS_EXPORT_TARGET=s3
DATABRICKS_EXPORT_BASE_PATH=/tmp/trading_lakehouse
S3_BUCKET_NAME=
S3_BASE_PREFIX=bronze/trading_alerts

# ------------------------------------------------------------
# Cron / Scheduler
# ------------------------------------------------------------
CRON_SECRET=
"@ | Out-File -FilePath ".env.example" -Encoding utf8
}
else {
    Write-Host "[INFO] .env.example ya existe."
}

# ============================================================
# 7. Crear .env local si no existe
# ============================================================

if (-not (Test-Path ".env")) {
    Write-Host "[INFO] Creando .env local desde .env.example..."
    Copy-Item ".env.example" ".env"
    Write-Host "[ACTION REQUIRED] Edita el archivo .env y completa los valores locales necesarios."
}
else {
    Write-Host "[INFO] .env ya existe. No se sobrescribe."
}

# ============================================================
# 8. Validación básica de estructura
# ============================================================

Write-Host ""
Write-Host "[INFO] Validando estructura básica del backend..."

$requiredPaths = @(
    "app",
    "app\main.py",
    "app\core",
    "app\services",
    "app\repositories",
    "app\utils"
)

foreach ($path in $requiredPaths) {
    if (Test-Path $path) {
        Write-Host "[OK] $path"
    }
    else {
        Write-Host "[WARN] No encontrado: $path"
    }
}

# ============================================================
# 9. Test de importación básica
# ============================================================

Write-Host ""
Write-Host "[INFO] Probando importación de app.main..."

python -c "from app.main import app; print('Import OK')"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Falló la importación de app.main."
    exit 1
}

# ============================================================
# 10. Resultado final
# ============================================================

Write-Host ""
Write-Host "============================================================"
Write-Host " Setup local completado"
Write-Host "============================================================"
Write-Host ""
Write-Host "Siguientes pasos:"
Write-Host "1. Edita .env y completa tus valores locales."
Write-Host "2. Ejecuta:"
Write-Host "   .\run_local.ps1"
Write-Host ""
```