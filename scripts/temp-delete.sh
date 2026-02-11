#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DRY_RUN=1
if [[ "${1:-}" == "--force" ]]; then
  DRY_RUN=0
fi

TARGETS=(
  ".cache/garbage"
  ".pytest_cache"
  "data/processed/logs"
  "corpus/check_*"
  "corpus/temp_upload_*"
  "corpus/img_*"
  "corpus/lec_*"
  "data/user_uploads/check_*"
  "data/user_uploads/temp_upload_*"
  "data/user_uploads/img_*"
  "data/user_uploads/lec_*"
  "data/models/mfa/data/run_*"
  "data/models/mfa/data/output_*"
  "data/processed/mfa_runs/*"
)

echo "Workspace cleanup target list:"
for pattern in "${TARGETS[@]}"; do
  echo "  - $pattern"
done

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo
  echo "Dry run mode. Re-run with '--force' to delete."
  exit 0
fi

shopt -s nullglob
for pattern in "${TARGETS[@]}"; do
  matches=( $pattern )
  for path in "${matches[@]}"; do
    rm -rf "$path"
    echo "Deleted: $path"
  done
done
shopt -u nullglob

echo "Cleanup complete."
