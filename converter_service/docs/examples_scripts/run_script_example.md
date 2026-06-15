### The example script to run Medroll Anonymization on Athena
The private data were removed, you should modificate this script using your data.

```bash
#!/bin/bash -l
#SBATCH -J medroll_api
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=12:00:00
#SBATCH -A ${SLURM_ACCOUNT:-your_grant_id}
#SBATCH -p ${SLURM_PARTITION:-plgrid-gpu-a100}
#SBATCH --gres=gpu:${GPUS:-8}
#SBATCH --mem=${MEM:-320G}
#SBATCH --output=medroll_api_%j.out
#SBATCH --error=medroll_api_%j.err

set -euo pipefail
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$PWD}"
cd "$PROJECT_ROOT"

# Load environment modules
module purge
module load GCCcore/13.2.0
module load Python/3.11.5
module load CUDA/12.1.1

# Configure virtual environment
VENV_DIR="${VENV_DIR:-$SCRATCH/medroll_venv}"
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# Install/Update dependencies
python3 -m pip install --upgrade pip
python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
python3 -m pip install -r converter_service/requirements.txt

# Load secrets (e.g., HF_TOKEN)
SECRETS_FILE=".job-secrets"
if [[ -f "$SECRETS_FILE" ]]; then
  set -a
  source "$SECRETS_FILE"
  set +a
else
  echo "WARNING: $SECRETS_FILE not found. Some features may fail." >&2
fi

# Environment optimizations
export PYTORCH_ALLOC_CONF="expandable_segments:True"
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_HOME="${HF_HOME:-$SCRATCH/huggingface_cache}"
mkdir -p "$HF_HOME"

echo "Running on $(hostname) with GPU: ${CUDA_VISIBLE_DEVICES:-unset}"

# Start the API
python3 -m uvicorn converter_service.api_converter:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1

```
