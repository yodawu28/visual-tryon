#!/bin/bash
# Setup script cho CatVTON local inference trên MacBook M-series
# Requires: MacBook Pro/Air với Apple Silicon (M1/M2/M3)

set -e

echo "=========================================="
echo "CatVTON Local Setup cho MacBook M-series"
echo "=========================================="

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "ERROR: Script này chỉ chạy trên macOS"
    exit 1
fi

# Check if Apple Silicon
if [[ $(uname -m) != "arm64" ]]; then
    echo "ERROR: Script này yêu cầu Apple Silicon (M1/M2/M3)"
    exit 1
fi

echo ""
echo "Step 1: Check/Install Miniforge..."
echo "------------------------------------"

# Check if conda installed
if ! command -v conda &> /dev/null; then
    echo "Miniforge chưa cài. Downloading Miniforge..."

    # Download Miniforge for Apple Silicon
    curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"

    # Install
    bash Miniforge3-MacOSX-arm64.sh -b -p $HOME/miniforge3

    # Initialize
    eval "$($HOME/miniforge3/bin/conda shell.bash hook)"
    conda init bash

    # Cleanup
    rm Miniforge3-MacOSX-arm64.sh

    echo "Miniforge installed successfully"
else
    echo "Miniforge đã cài sẵn"
fi

# Source conda
eval "$(conda shell.bash hook)"

echo ""
echo "Step 2: Create Conda Environment..."
echo "------------------------------------"

ENV_NAME="tryon-catvton"

# Check if environment exists
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "Environment '${ENV_NAME}' đã tồn tại. Removing..."
    conda env remove -n ${ENV_NAME} -y
fi

# Create new environment with Python 3.11
echo "Creating new environment: ${ENV_NAME}"
conda create -n ${ENV_NAME} python=3.11 -y

# Activate environment using source (works without conda init in current shell)
echo "Activating environment: ${ENV_NAME}"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate ${ENV_NAME}

echo ""
echo "Step 3: Install PyTorch Nightly với MPS Support..."
echo "----------------------------------------------------"

# Install PyTorch nightly for Apple Silicon với MPS
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cpu

echo ""
echo "Step 4: Install Diffusers và Dependencies..."
echo "---------------------------------------------"

# Install diffusers and related packages
pip install diffusers[torch] transformers accelerate safetensors

# Install additional dependencies
pip install pillow numpy

echo ""
echo "Step 5: Test MPS Availability..."
echo "---------------------------------"

python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'MPS available: {torch.backends.mps.is_available()}')
print(f'MPS built: {torch.backends.mps.is_built()}')

if torch.backends.mps.is_available():
    print('✓ MPS backend ready for CatVTON inference')
else:
    print('✗ MPS not available. Check PyTorch installation.')
    exit(1)
"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart shell hoặc run:"
echo "   source ~/.bash_profile  # for bash"
echo "   source ~/.zshrc         # for zsh"
echo ""
echo "2. Then activate environment:"
echo "   conda activate ${ENV_NAME}"
echo ""
echo "2. Set IMAGE_GEN_MODE=local trong .env"
echo ""
echo "3. Configure CatVTON settings trong .env:"
echo "   CATVTON_MODEL_ID=zhengchong/CatVTON"
echo "   CATVTON_DEVICE=mps"
echo "   CATVTON_ENABLE_ATTENTION_SLICING=true"
echo "   CATVTON_ENABLE_VAE_SLICING=true"
echo "   CATVTON_ENABLE_CPU_OFFLOAD=true"
echo ""
echo "4. Install app dependencies:"
echo "   pip install -r requirements.txt"
echo ""
echo "5. Run server:"
echo "   python -m uvicorn src.main:app --reload"
echo ""
