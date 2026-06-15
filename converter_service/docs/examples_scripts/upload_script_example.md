### The example script to upload Medroll Anonymization to Athena
The private data were removed, you should modificate this script using your data.

```bash
#!/usr/bin/env bash

set -euo pipefail

KEY_PATH="$1"
LOGIN="$2"

HOST="${HOST:-athena.cyfronet.pl}"
REMOTE_DIR="${REMOTE_DIR:-~/medroll}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "$KEY_PATH" ]]; then
  echo "ERROR: The SSH key not found in: $KEY_PATH" >&2
  exit 1
fi


chmod 600 "$KEY_PATH"

echo "---  I start synchronization on $HOST ---"


ssh -i "$KEY_PATH" "$LOGIN@$HOST" "mkdir -p $REMOTE_DIR"

rsync -avz -e "ssh -i \"$KEY_PATH\"" \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude '.git' \
  --exclude '*.out' \
  --exclude '*.err' \
  --exclude 'results' \
  --exclude 'work' \
  "$ROOT_DIR/" "$LOGIN@$HOST:$REMOTE_DIR/"

echo "--- The sychronization was finished! ---"