#!/bin/bash
# Helper script to activate CatVTON environment
# Usage: source scripts/activate_catvton.sh

ENV_NAME="tryon-catvton"

# Check if conda available
if ! command -v conda &> /dev/null; then
    echo "ERROR: conda not found in PATH"
    echo "Add to your shell config (~/.zshrc or ~/.bash_profile):"
    echo ""
    echo "# Conda initialization"
    echo "eval \"\$(conda shell.bash hook)\""
    return 1
fi

# Initialize conda for current shell if not already done
if ! type conda | grep -q "function"; then
    echo "Initializing conda for current shell..."

    # Get conda base path
    CONDA_BASE=$(conda info --base)

    if [ -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]; then
        source "${CONDA_BASE}/etc/profile.d/conda.sh"
    else
        echo "ERROR: Could not find conda.sh"
        return 1
    fi
fi

# Check if environment exists
if ! conda env list | grep -q "^${ENV_NAME} "; then
    echo "ERROR: Environment '${ENV_NAME}' không tồn tại"
    echo "Run setup script first:"
    echo "  bash scripts/setup_catvton_macos.sh"
    return 1
fi

# Activate environment
echo "Activating ${ENV_NAME}..."
conda activate ${ENV_NAME}

echo ""
echo "✓ Environment activated: ${ENV_NAME}"
echo "Python: $(python --version)"
echo ""
echo "To deactivate: conda deactivate"
echo ""
