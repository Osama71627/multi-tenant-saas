#!/usr/bin/env bash
# Reproducible release identity (Phase "production readiness conditions",
# Priority 9): git commit -> image build -> identifiable tag -> deploy.
#
# Registry: ghcr.io, under this repo's own GitHub account -- verified
# working with the same `gh auth token` already used to push/manage this
# repo (no separate credential was invented; `docker login ghcr.io`
# genuinely succeeded with it). Push is opt-in (PUSH=1) since not every
# invocation of this script should publish images.
#
# Usage: infra/build-images.sh          # build + tag only
#        PUSH=1 infra/build-images.sh   # build + tag + push to ghcr.io
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

REGISTRY="${REGISTRY:-ghcr.io/osama71627/multi-tenant-saas}"

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

if [ "${PUSH:-0}" = "1" ]; then
    echo "Pushing to ${REGISTRY} ..."
    for name in backend storefront dashboard platform-admin; do
        docker tag "saas-${name}:${SHA}" "${REGISTRY}-${name}:${SHA}"
        docker push "${REGISTRY}-${name}:${SHA}"
    done
    echo "Pushed. Pull with, e.g.: docker pull ${REGISTRY}-backend:${SHA}"
fi

echo
echo "Deployment identity: record this SHA alongside wherever these images"
echo "are deployed (a deploy log, the runbook, or a registry tag) so a"
echo "running container can always be traced back to the exact commit that"
echo "produced it -- see runbooks/deploy.md."
