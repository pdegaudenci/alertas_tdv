# ============================================================
# run.ps1
# Run local FastAPI backend with Databricks/GCS export enabled
# ============================================================

Write-Host ""
Write-Host "========================================="
Write-Host " RUN - Trading Backend Local"
Write-Host "========================================="
Write-Host ""

# ------------------------------------------------------------
# 1. Check current folder
# ------------------------------------------------------------

if (-Not (Test-Path "app")) {
    Write-Host "ERROR: app/ folder not found."
    Write-Host "Run this script from the backend/ folder."
    exit 1
}

if (-Not (Test-Path ".venv")) {
    Write-Host "ERROR: .venv not found."
    Write-Host "Run setup first:"
    Write-Host ".\setup.ps1"
    exit 1
}

# ------------------------------------------------------------
# 2. Activate virtual environment
# ------------------------------------------------------------

Write-Host "Activating virtual environment..."
& ".\.venv\Scripts\Activate.ps1"

# ------------------------------------------------------------
# 3. GCP credentials path
# ------------------------------------------------------------

$GcpCredentialsPath = Join-Path (Get-Location) "credentials\service_account_gcs_writer.json"

if (-Not (Test-Path $GcpCredentialsPath)) {
    Write-Host ""
    Write-Host "ERROR: GCP credentials file not found:"
    Write-Host $GcpCredentialsPath
    Write-Host ""
    Write-Host "Place your service account JSON in:"
    Write-Host "backend\credentials\service_account_gcs_writer.json"
    Write-Host ""
    exit 1
}

# ------------------------------------------------------------
# 4. Environment variables - Databricks/GCS export
# ------------------------------------------------------------

$env:ENABLE_DATABRICKS_EXPORT = "true"
$env:DATABRICKS_EXPORT_TARGET = "gcs"
$env:GCS_BUCKET_NAME = "trading-lakehouse-btc"
$env:GCS_BASE_PREFIX = "bronze/trading_alerts"
$env:GOOGLE_APPLICATION_CREDENTIALS = $GcpCredentialsPath

# ------------------------------------------------------------
# 5. Optional local backend vars
# ------------------------------------------------------------
# Uncomment and adjust if needed:
#
# $env:WEBHOOK_SECRET = "MI_SECRET"
# $env:TELEGRAM_ENABLED = "false"
# $env:SUPABASE_URL = "https://xxxx.supabase.co"
# $env:SUPABASE_SERVICE_ROLE_KEY = "xxxx"
# $env:ALLOWED_ORIGINS = "*"

# ------------------------------------------------------------
# 6. Show effective config
# ------------------------------------------------------------

Write-Host "Databricks export enabled: $env:ENABLE_DATABRICKS_EXPORT"
Write-Host "Databricks export target : $env:DATABRICKS_EXPORT_TARGET"
Write-Host "GCS bucket                : $env:GCS_BUCKET_NAME"
Write-Host "GCS prefix                : $env:GCS_BASE_PREFIX"
Write-Host "GCP credentials           : $env:GOOGLE_APPLICATION_CREDENTIALS"
Write-Host ""

# ------------------------------------------------------------
# 7. Run FastAPI
# ------------------------------------------------------------

Write-Host "Starting FastAPI..."
Write-Host "URL: http://localhost:8000"
Write-Host ""

uvicorn app.main:app --reload