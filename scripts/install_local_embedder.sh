#!/usr/bin/env bash
set -e

if python3 - <<PY
try:
    import sentence_transformers  # noqa: F401
    print("sentence-transformers already installed")
except Exception:
    raise SystemExit(1)
PY
then
    exit 0
fi

echo "Installing sentence-transformers for local embeddings..."
pip install --break-system-packages sentence-transformers
echo "Done. Set EMBEDDING_BACKEND=local (and optionally LOCAL_EMBED_MODEL) to enable."
