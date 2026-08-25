#!/usr/bin/env bash
# Reproducible release identity (Phase "production readiness conditions",
# Priority 9): git commit -> image build -> identifiable tag -> deploy.
#
# Deliberately NOT a registry/CI pipeline -- this project has neither a
# remote git host nor a chosen container registry configured yet (see
# runbooks/README.md and the Phase 20/21 audit). This script is the
# reproducible-tagging half of that requirement, usable locally today;
# `docker push` to a real registry is a one-line addition once a registry
# and its authentication are actually chosen -- do not invent one here.
#
# Usage: infra/build-images.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "No git repository -- a commit-identified tag requires one. See Priority 1." >&2
    exit 1
fi

SHA=$(git rev-parse --short HEAD)
if [ -n "$(git status --porcelain)" ]; then
    SHA="${SHA}-dirty"
    echo "WARNING: working tree has uncommitted changes -- tag is marked '-dirty'." >&2
fi

echo "Building images for commit ${SHA} ..."

docker build -t "saas-backend:${SHA}" -t saas-backend:latest ./backend

for app in storefront dashboard platform-admin; do
    docker build -t "saas-${app}:${SHA}" -t "saas-${app}:latest" \
        --build-arg "APP=${app}" \
        --build-arg NEXT_PUBLIC_BACKEND_PORT="${NEXT_PUBLIC_BACKEND_PORT:-8443}" \
        ./frontend
done

echo "Built and tagged with ${SHA} (and :latest):"
docker images --format '{{.Repository}}:{{.Tag}}' | grep ":${SHA}$"

echo
echo "Deployment identity: record this SHA alongside wherever these images"
echo "are deployed (a deploy log, the runbook, or a registry tag) so a"
echo "running container can always be traced back to the exact commit that"
echo "produced it -- see runbooks/deploy.md."
