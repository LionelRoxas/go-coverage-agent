#!/usr/bin/env bash
# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
# Re-measures an evidence folder's committed tests on a fresh clone of montanaflynn/stats, in a plain Go container:
# no app code, no LLM. Usage: scripts/verify-evidence.sh docs/evidence/stats-8c38d392ecaf
# Works from Git Bash on Windows (MSYS_NO_PATHCONV, host path as C:/...) and on macOS / Linux. Needs Docker.
set -euo pipefail

REPO_URL=https://github.com/montanaflynn/stats
COMMIT=c2cb6881295ee9249914cce7bcb80dc96ee2f4b2

dir=${1:?usage: scripts/verify-evidence.sh <evidence-dir>}
[ -d "$dir/tests" ] || { echo "no tests folder in $dir" >&2; exit 2; }
root=$(cd "$(dirname "$0")/.." && pwd)
go_version=$(tr -d '[:space:]' < "$root/.go-version")
# Git Bash: `pwd -W` gives C:/... (what Docker Desktop mounts); elsewhere it fails and plain `pwd` is used.
tests=$(cd "$dir/tests" && { pwd -W 2>/dev/null || pwd; })
export MSYS_NO_PATHCONV=1

echo "== $dir: $(find "$dir/tests" -name '*_test.go' | wc -l | tr -d ' ') test files, golang:$go_version, stats@$COMMIT"
# The app measured the module's packages minus its default exclude patterns (examples/**, testdata/**), so the
# same packages are measured here; `go vet` checks everything.
docker run --rm -v "$tests:/evidence:ro" "golang:$go_version" sh -ec "
  git clone -q $REPO_URL /src
  cd /src
  git -c advice.detachedHead=false checkout -q $COMMIT
  find . -name '*_test.go' -delete
  cp -R /evidence/. .
  go vet ./...
  pkgs=\$(go list ./... | grep -Ev '/(examples|testdata)(/|\$)')
  go test -count=1 -covermode=set -coverprofile=/tmp/cover.out \$pkgs
  go tool cover -func=/tmp/cover.out | tail -n 1
  # two decimals, as the app reports it: covered statements / statements, over distinct blocks of the profile
  awk 'NR > 1 { n[\$1] = \$2; if (\$3 > 0) c[\$1] = 1 } END { for (b in n) { t += n[b]; if (b in c) k += n[b] }
       printf \"total coverage: %.2f%% (%d of %d statements)\n\", 100 * k / t, k, t }' /tmp/cover.out
"
