# Installation Guide

Complete installation guide for the SHAKTI-CHAIN V2G ML Platform.

## System Requirements

### Minimum Requirements
- **OS**: Windows 10/11, Linux (Ubuntu 20.04+), macOS 10.15+
- **Python**: 3.10 or higher
- **RAM**: 8GB
- **Storage**: 10GB free space
- **CPU**: Multi-core processor (4+ cores recommended)

### Recommended Requirements
- **RAM**: 16GB+
- **GPU**: NVIDIA GPU with CUDA 11.8+ (for faster training)
- **Storage**: 50GB+ SSD

## Installation Methods

### Method 1: Automated Setup (Recommended)

#### On Windows

1. **Open PowerShell as Administrator**

2. **Navigate to project directory**
   ```powershell
   cd ShaktiChain\ml
   ```

3. **Run setup script**
   ```powershell
   .\setup.ps1
   ```

4. **Follow prompts**
   - Confirm Python version
   - Choose whether to install dev dependencies
   - Script will create venv, install packages, and set up directories

#### On Linux/macOS

1. **Open terminal**

2. **Navigate to project directory**
   ```bash
   cd ShaktiChain/ml
   ```

3. **Make setup script executable**
   ```bash
   chmod +x setup.sh
   ```

4. **Run setup script**
   ```bash
   ./setup.sh
   ```

5. **Follow prompts**

### Method 2: Manual Setup

#### Step 1: Check Python Version

```bash
python --version
# Should show Python 3.10.x or higher
```

If Python 3.10+ is not installed:

**Windows:**
- Download from https://www.python.org/downloads/
- Check "Add Python to PATH" during installation

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip
```

**macOS:**
```bash
brew install python@3.10
```

#### Step 2: Create Virtual Environment

```bash
# Navigate to project directory
cd ShaktiChain/ml

# Create virtual environment
python -m venv venv
```

#### Step 3: Activate Virtual Environment

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate.bat
```

**Linux/macOS:**
```bash
source venv/bin/activate
```

You should see `(venv)` prefix in your terminal.

#### Step 4: Upgrade pip

```bash
python -m pip install --upgrade pip
```

#### Step 5: Install Package

**Standard Installation:**
```bash
pip install -e .
```

**With Development Tools:**
```bash
pip install -e ".[dev]"
```

#### Step 6: Verify Installation

```bash
python -c "import torch; import pytorch_lightning; import mlflow; print('All packages imported successfully!')"
```

#### Step 7: Set Up Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your favorite editor
nano .env  # or vim, code, notepad, etc.
```

Add your API keys:
```bash
OPENWEATHER_API_KEY=your_api_key_here
```

#### Step 8: Initialize DVC

```bash
dvc init
```

#### Step 9: Create Directories

```bash
# Windows
mkdir data\raw data\processed data\features models logs\mlruns logs\tensorboard

# Linux/macOS
mkdir -p data/{raw,processed,features} models logs/{mlruns,tensorboard}
```

### Method 3: Using Conda

If you prefer Conda:

```bash
# Create conda environment
conda create -n shakti python=3.10

# Activate environment
conda activate shakti

# Install PyTorch (with CUDA if available)
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia

# Install other dependencies
pip install -e .

# Initialize DVC
dvc init
```

## GPU Setup (Optional but Recommended)

### NVIDIA GPU with CUDA

1. **Check GPU availability**
   ```bash
   nvidia-smi
   ```

2. **Install CUDA Toolkit** (if not installed)
   - Download from https://developer.nvidia.com/cuda-downloads
   - Version 11.8 or 12.1 recommended

3. **Install PyTorch with CUDA**
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

4. **Verify GPU support**
   ```python
   python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
   ```

### AMD GPU with ROCm (Linux only)

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

## Getting API Keys

### OpenWeatherMap (Required for real weather data)

1. Go to https://openweathermap.org/api
2. Click "Sign Up" (free tier available)
3. Verify email
4. Go to API keys section
5. Copy your API key
6. Add to `.env` file:
   ```
   OPENWEATHER_API_KEY=your_key_here
   ```

**Note**: Free tier includes:
- 1,000 calls/day
- 60 calls/minute
- Current weather data
- 5-day forecast

For historical data (paid):
- Historical Weather API required
- Costs vary by usage

## Verification

### Test Installation

Run the demo script:

```bash
python scripts/demo.py
```

Expected output:
```
============================================================
SHAKTI-CHAIN V2G ML Platform Demo
============================================================

Step 1: Data Collection
------------------------------------------------------------
Collecting calendar data...
✓ Collected 168 calendar records
Collecting weather data...
✓ Collected 336 weather records

Step 2: Data Preprocessing
------------------------------------------------------------
...
```

### Test Individual Components

**Test data collectors:**
```bash
pytest tests/test_collectors.py -v
```

**Test imports:**
```python
python -c "
from src.data.collectors import POSOCOCollector, IEXCollector
from src.models import LSTMForecaster, TransformerForecaster
from src.training import ForecastingLightningModule
print('All imports successful!')
"
```

### Check Installed Packages

```bash
pip list | grep -E "(torch|lightning|mlflow|dvc|hydra)"
```

Expected output:
```
dvc                    3.x.x
hydra-core             1.3.x
mlflow                 2.9.x
pytorch-lightning      2.1.x
torch                  2.1.x
...
```

## Troubleshooting

### Issue: "Python not found"

**Solution:**
- Ensure Python 3.10+ is installed
- Add Python to PATH (Windows)
- Use `python3` instead of `python` (Linux/macOS)

### Issue: "pip: command not found"

**Solution:**
```bash
# Linux/macOS
sudo apt install python3-pip  # Ubuntu/Debian
brew install python           # macOS

# Or use python -m pip
python -m pip install --upgrade pip
```

### Issue: "Permission denied" (Linux/macOS)

**Solution:**
```bash
# Don't use sudo with pip
# If you see permission errors:
pip install --user -e .

# Or use virtual environment (recommended)
python -m venv venv
source venv/bin/activate
pip install -e .
```

### Issue: "Microsoft Visual C++ required" (Windows)

**Solution:**
- Download and install: https://visualstudio.microsoft.com/downloads/
- Select "Desktop development with C++"
- Or install "Build Tools for Visual Studio"

### Issue: "CUDA out of memory"

**Solution:**
```bash
# Use CPU instead
python scripts/train.py training.accelerator=cpu

# Or reduce batch size
python scripts/train.py data.loader.batch_size=16
```

### Issue: "ModuleNotFoundError: No module named 'src'"

**Solution:**
```bash
# Make sure you installed in editable mode
pip install -e .

# Verify installation
pip show shakti-chain-ml
```

### Issue: DVC init fails

**Solution:**
```bash
# Remove existing .dvc directory
rm -rf .dvc

# Reinitialize
dvc init --no-scm  # If not using git
# or
dvc init           # If using git
```

## Updating

### Update Dependencies

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Update all packages
pip install --upgrade -e .

# Or update specific package
pip install --upgrade mlflow
```

### Update from Git

```bash
git pull origin main
pip install --upgrade -e .
```

## Uninstalling

### Remove Virtual Environment

```bash
# Deactivate if active
deactivate

# Remove directory
rm -rf venv  # Linux/macOS
rmdir /s venv  # Windows
```

### Remove Package

```bash
pip uninstall shakti-chain-ml
```

### Clean Generated Files

```bash
# Using Makefile
make clean

# Manual
rm -rf __pycache__ *.pyc .pytest_cache .coverage htmlcov build dist *.egg-info
```

## Next Steps

After successful installation:

1. **Read the Quick Start Guide**
   ```bash
   cat QUICKSTART.md
   ```

2. **Run the demo**
   ```bash
   python scripts/demo.py
   ```

3. **Collect data**
   ```bash
   python scripts/collect_data.py
   ```

4. **Train a model**
   ```bash
   python scripts/train.py
   ```

5. **View results**
   ```bash
   mlflow ui
   ```

## Support

If you encounter issues not covered here:

1. Check [README.md](README.md) for detailed documentation
2. Check [QUICKSTART.md](QUICKSTART.md) for usage examples
3. Search existing issues on GitHub
4. Open a new issue with:
   - Operating system and version
   - Python version
   - Error message
   - Steps to reproduce

## Additional Resources

- **PyTorch Documentation**: https://pytorch.org/docs/
- **PyTorch Lightning**: https://lightning.ai/docs/pytorch/
- **MLflow Documentation**: https://mlflow.org/docs/
- **Hydra Documentation**: https://hydra.cc/docs/
- **DVC Documentation**: https://dvc.org/doc
