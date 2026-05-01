# ============================================================
# run_local_s3.ps1
# Ejecuta backend FastAPI local leyendo variables desde .env
# ============================================================

Write-Host "Cargando variables desde .env..." -ForegroundColor Cyan

$envFile = ".env"

if (-Not (Test-Path $envFile)) {
    Write-Host "No se encontró archivo .env en la ruta actual." -ForegroundColor Red
    Write-Host "Crea un archivo .env antes de ejecutar este script." -ForegroundColor Yellow
    exit 1
}

Get-Content $envFile | ForEach-Object {
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

    $key, $value = $line -split "=", 2

    $key = $key.Trim()
    $value = $value.Trim()

    # Quitar comillas simples o dobles si existen
    if (
        ($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))
    ) {
        $value = $value.Substring(1, $value.Length - 2)
    }

    [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
}

Write-Host "Variables cargadas correctamente." -ForegroundColor Green

Write-Host "Resumen de configuración no sensible:" -ForegroundColor Cyan
Write-Host "ENABLE_DATABRICKS_EXPORT=$env:ENABLE_DATABRICKS_EXPORT"
Write-Host "DATABRICKS_EXPORT_TARGET=$env:DATABRICKS_EXPORT_TARGET"
Write-Host "S3_BUCKET_NAME=$env:S3_BUCKET_NAME"
Write-Host "S3_BASE_PREFIX=$env:S3_BASE_PREFIX"
Write-Host "AWS_REGION=$env:AWS_REGION"

if (-not $env:AWS_ACCESS_KEY_ID) {
    Write-Host "AWS_ACCESS_KEY_ID no está definido." -ForegroundColor Red
    exit 1
}

if (-not $env:AWS_SECRET_ACCESS_KEY) {
    Write-Host "AWS_SECRET_ACCESS_KEY no está definido." -ForegroundColor Red
    exit 1
}

Write-Host "AWS credentials detectadas en entorno del proceso." -ForegroundColor Green
Write-Host "Iniciando FastAPI..." -ForegroundColor Cyan

uvicorn app.main:app --reload