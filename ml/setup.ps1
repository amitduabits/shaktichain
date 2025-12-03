# SHAKTI-CHAIN ML Platform Setup Script (PowerShell)

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "SHAKTI-CHAIN ML Platform Setup" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($pythonVersion -match "Python (\d+\.\d+)") {
    $version = [version]$matches[1]
    if ($version -lt [version]"3.10") {
        Write-Host "Error: Python 3.10 or higher is required. Found: $pythonVersion" -ForegroundColor Red
        exit 1
    }
    Write-Host "Python version: $pythonVersion ✓" -ForegroundColor Green
}
Write-Host ""

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "Virtual environment already exists" -ForegroundColor Yellow
} else {
    python -m venv venv
    Write-Host "Virtual environment created ✓" -ForegroundColor Green
}
Write-Host ""

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"
Write-Host "Virtual environment activated ✓" -ForegroundColor Green
Write-Host ""

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip
Write-Host "pip upgraded ✓" -ForegroundColor Green
Write-Host ""

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -e .
Write-Host "Dependencies installed ✓" -ForegroundColor Green
Write-Host ""

# Install development dependencies (optional)
$devInstall = Read-Host "Install development dependencies? (y/n)"
if ($devInstall -eq "y" -or $devInstall -eq "Y") {
    pip install -e ".[dev]"
    Write-Host "Development dependencies installed ✓" -ForegroundColor Green
}
Write-Host ""

# Create .env file
Write-Host "Setting up environment..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env file created from .env.example" -ForegroundColor Green
    Write-Host "Please edit .env with your API keys" -ForegroundColor Yellow
} else {
    Write-Host ".env file already exists" -ForegroundColor Yellow
}
Write-Host ""

# Initialize DVC
Write-Host "Initializing DVC..." -ForegroundColor Yellow
if (-not (Test-Path ".dvc")) {
    dvc init
    Write-Host "DVC initialized ✓" -ForegroundColor Green
} else {
    Write-Host "DVC already initialized" -ForegroundColor Yellow
}
Write-Host ""

# Create necessary directories
Write-Host "Creating directories..." -ForegroundColor Yellow
$directories = @(
    "data\raw",
    "data\processed",
    "data\features",
    "models",
    "logs\mlruns",
    "logs\tensorboard",
    "notebooks"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "Directories created ✓" -ForegroundColor Green
Write-Host ""

# Setup complete
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env with your API keys"
Write-Host "2. Run 'python scripts/collect_data.py' to collect data"
Write-Host "3. Run 'python scripts/preprocess_data.py' to preprocess data"
Write-Host "4. Run 'python scripts/train.py' to train a model"
Write-Host "5. Run 'mlflow ui' to view experiments"
Write-Host ""
Write-Host "For more information, see README.md" -ForegroundColor Cyan
