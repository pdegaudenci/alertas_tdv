# ============================================================
# setup.ps1
# Setup local backend environment for TradingView Validation Layer
# ============================================================

Write-Host ""
Write-Host "========================================="
Write-Host " SETUP - Trading Backend Local Environment"
Write-Host "========================================="
Write-Host ""

# ------------------------------------------------------------
# 1. Check current folder
# ------------------------------------------------------------

if (-Not (Test-Path "requirements.txt")) {
    Write-Host "ERROR: requirements.txt not found."
    Write-Host "Run this script from the backend/ folder."
    exit 1
}

if (-Not (Test-Path "app")) {
    Write-Host "ERROR: app/ folder not found."
    Write-Host "Run this script from the backend/ folder."
    exit 1
}

# ------------------------------------------------------------
# 2. Create virtual environment
# ------------------------------------------------------------

if (-Not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
} else {
    Write-Host "Virtual environment already exists."
}

# ------------------------------------------------------------
# 3. Activate virtual environment
# ------------------------------------------------------------

Write-Host "Activating virtual environment..."
& ".\.venv\Scripts\Activate.ps1"

# ------------------------------------------------------------
# 4. Upgrade pip
# ------------------------------------------------------------

Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

# ------------------------------------------------------------
# 5. Ensure GCS dependency is present in requirements.txt
# ------------------------------------------------------------

$requirementsContent = Get-Content "requirements.txt" -Raw

if ($requirementsContent -notmatch "google-cloud-storage") {
    Write-Host "Adding google-cloud-storage to requirements.txt..."
    Add-Content -Path "requirements.txt" -Value "`ngoogle-cloud-storage>=2.16.0"
} else {
    Write-Host "google-cloud-storage already present in requirements.txt."
}

# ------------------------------------------------------------
# 6. Install requirements
# ------------------------------------------------------------

Write-Host "Installing requirements..."
pip install -r requirements.txt

# ------------------------------------------------------------
# 7. Create credentials folder if missing
# ------------------------------------------------------------

if (-Not (Test-Path "credentials")) {
    Write-Host "Creating credentials/ folder..."
    New-Item -ItemType Directory -Path "credentials" | Out-Null
} else {
    Write-Host "credentials/ folder already exists."
}

# ------------------------------------------------------------
# 8. Credential reminder
# ------------------------------------------------------------

$defaultCredentialPath = ".\credentials\service_account_gcs_writer.json"

if (-Not (Test-Path $defaultCredentialPath)) {
    Write-Host ""
    Write-Host "WARNING: GCP credentials file not found:"
    Write-Host $defaultCredentialPath
    Write-Host ""
    Write-Host "Place your GCP service account JSON here:"
    Write-Host "backend\credentials\service_account_gcs_writer.json"
    Write-Host ""
} else {
    Write-Host "GCP credentials found:"
    Write-Host $defaultCredentialPath
}

# ------------------------------------------------------------
# 9. Final message
# ------------------------------------------------------------

Write-Host ""
Write-Host "========================================="
Write-Host " SETUP COMPLETED"
Write-Host "========================================="
Write-Host ""
Write-Host "Next step:"
Write-Host ".\run.ps1"
Write-Host ""