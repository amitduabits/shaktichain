#!/bin/bash

# SHAKTI-CHAIN ML Platform Setup Script

echo "=================================="
echo "SHAKTI-CHAIN ML Platform Setup"
echo "=================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )(.+)')
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python 3.10 or higher is required. Found: $python_version"
    exit 1
fi

echo "Python version: $python_version ✓"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists"
else
    python3 -m venv venv
    echo "Virtual environment created ✓"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || source venv/Scripts/activate
echo "Virtual environment activated ✓"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip
echo "pip upgraded ✓"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -e .
echo "Dependencies installed ✓"
echo ""

# Install development dependencies (optional)
read -p "Install development dependencies? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip install -e ".[dev]"
    echo "Development dependencies installed ✓"
fi
echo ""

# Create .env file
echo "Setting up environment..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ".env file created from .env.example"
    echo "Please edit .env with your API keys"
else
    echo ".env file already exists"
fi
echo ""

# Initialize DVC
echo "Initializing DVC..."
if [ ! -d ".dvc" ]; then
    dvc init
    echo "DVC initialized ✓"
else
    echo "DVC already initialized"
fi
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p data/{raw,processed,features}
mkdir -p models
mkdir -p logs/{mlruns,tensorboard}
mkdir -p notebooks
echo "Directories created ✓"
echo ""

# Setup complete
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit .env with your API keys"
echo "2. Run 'python scripts/collect_data.py' to collect data"
echo "3. Run 'python scripts/preprocess_data.py' to preprocess data"
echo "4. Run 'python scripts/train.py' to train a model"
echo "5. Run 'mlflow ui' to view experiments"
echo ""
echo "For more information, see README.md"
