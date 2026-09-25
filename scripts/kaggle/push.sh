#!/bin/bash
# Launch / watch / collect a RoomRecon job on Kaggle (T2) with the official Kaggle CLI.
# Works from Git Bash (e.g. the VS Code terminal) or WSL. Setup steps: m1_t2/README.md.
#
#   bash push.sh login                   sign in through the browser (once)
#   bash push.sh <job> check             confirm the CLI is installed and signed in
#   bash push.sh <job> push              run the job's entry script on Kaggle at this commit
#   bash push.sh <job> push --continue   same, with the job's previous output attached, so
#                                        finished runs are skipped and interrupted ones resume
#   bash push.sh <job> status            queued / running / complete / error
#   bash push.sh <job> fetch             download the results to <job>/output/, check the verdict
#
# A job is a folder next to this script holding kernel-metadata.json and job.env:
#   SLUG       Kaggle kernel slug
#   ENTRY      script the session runs, relative to the repo (e.g. scripts/run_t2.sh)
#   ARTIFACT   results tarball the entry script writes next to verdict.json
#   ATTACH     optional: slugs of other jobs whose latest output is attached as input
#   PASS_ENV   optional: environment variables forwarded into the session when set here
#   JOB_FILES  optional: extra repo files the session runs, checked for being committed
#
# The notebook is generated, never edited by hand: it clones this repo at the exact commit
# being pushed and runs ENTRY. All logic lives in the repo, where it is tested.
# Optional: KAGGLE_DATASET=<owner>/<slug> attaches a Kaggle dataset as well.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
GIT_URL=https://github.com/asw-beep/RoomRecon.git
export PIP_NO_CACHE_DIR=1   # nothing piles up in the pip cache on C:
export PYTHONUTF8=1         # Windows' default codepage cannot encode the Kaggle log (T2 run 1)

# the `kaggle` launcher may not be on PATH with the Microsoft Store Python; call the module then
kg() {
  if command -v kaggle >/dev/null 2>&1; then kaggle "$@"
  else python -c "import sys; from kaggle.cli import main; sys.argv[0]='kaggle'; main()" "$@"; fi
}
python -c "import kaggle" >/dev/null 2>&1 || { echo "Kaggle CLI missing: python -m pip install --no-cache-dir kaggle"; exit 1; }

if [ "${1:-}" = login ]; then       # browser sign-in; needs no job or username yet
  kg auth login; exit
fi

JOB="${1:-}"; shift || true
JOBDIR="$HERE/$JOB"
[ -n "$JOB" ] && [ -f "$JOBDIR/job.env" ] \
  || { echo "usage: bash push.sh login | <job> check|push [--continue]|status|fetch"
       echo "jobs: $(cd "$HERE" && ls -d */ 2>/dev/null | tr -d / | tr '\n' ' ')"; exit 2; }
SLUG= ENTRY= ARTIFACT= ATTACH= PASS_ENV= JOB_FILES=
# shellcheck disable=SC1091
source "$JOBDIR/job.env"
[ -n "$SLUG" ] && [ -n "$ENTRY" ] && [ -n "$ARTIFACT" ] || { echo "$JOBDIR/job.env must set SLUG, ENTRY, ARTIFACT"; exit 2; }

USER_NAME="${KAGGLE_USERNAME:-}"
CFG="${KAGGLE_CONFIG_DIR:-$HOME/.kaggle}"
if [ -z "$USER_NAME" ] && [ -f "$CFG/kaggle.json" ]; then
  USER_NAME=$(python -c "import json,sys;print(json.load(open(sys.argv[1]))['username'])" "$CFG/kaggle.json")
fi
[ -n "$USER_NAME" ] || { echo "Set your Kaggle username:  export KAGGLE_USERNAME=<name from your kaggle.com profile URL>"; exit 1; }

# Nothing reaches Kaggle that is not committed, on GitHub, and passing the unit tests:
# a GPU session is the most expensive place to find a bug (T2 run 1 lost its outputs to a
# parse error a two-line test catches).
preflight() {
  # Only what the session runs must match the pushed commit; doc edits cannot change a run.
  local run_paths=(scripts configs tests)
  git -C "$REPO" diff --quiet HEAD -- "${run_paths[@]}" \
    || { echo "uncommitted changes under ${run_paths[*]} - commit first"; return 1; }
  # shellcheck disable=SC2086
  [ -z "$(git -C "$REPO" ls-files --others --exclude-standard -- "$ENTRY" scripts/setup_t2.sh \
          scripts/train.py scripts/verify_env.py scripts/gpu.py scripts/patches configs $JOB_FILES)" ] \
    || { echo "files the session runs are not committed - commit first"; return 1; }
  git -C "$REPO" fetch -q origin
  [ -n "$(git -C "$REPO" branch -r --contains HEAD)" ] \
    || { echo "HEAD $(git -C "$REPO" rev-parse --short HEAD) is not on origin - push it first (Kaggle clones from GitHub)"; return 1; }
  bash -n "$REPO/$ENTRY" && bash -n "$REPO/scripts/setup_t2.sh" || return 1
  (cd "$REPO" && python -m unittest discover -s tests -t . -q) || { echo "unit tests fail - not pushing"; return 1; }
}

# notebook <sha> <continue:0|1>: one %%bash cell. %%bash raises on a non-zero exit, so the
# Kaggle status follows the entry script's exit code, which is the job's verdict. The clone
# goes to /tmp so the repo does not end up in the session output.
notebook() {
  local pass="" v
  for v in $PASS_ENV; do [ -n "${!v:-}" ] && pass+="$v=${!v} "; done
  python - "$1" "$GIT_URL" "$2" "$ENTRY" "$JOB" "$pass" <<'EOF'
import json, shlex, sys
sha, url, cont, entry, job, passed = sys.argv[1:7]
pairs = [("ROOMRECON_T2_CONTINUE", int(cont))] + [tuple(p.split("=", 1)) for p in passed.split()]
env = "".join(f"export {k}={shlex.quote(str(v))}\n" for k, v in pairs)
src = f"""%%bash
# Generated by scripts/kaggle/push.sh ({job}) - do not edit. RoomRecon @ {sha}
set -euo pipefail
{env}rm -rf /tmp/RoomRecon
git clone -q {url} /tmp/RoomRecon
git -C /tmp/RoomRecon checkout -q {sha}
bash /tmp/RoomRecon/{entry}
"""
nb = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                 "source": src.splitlines(keepends=True)}],
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}
print(json.dumps(nb, indent=1))
EOF
}

# metadata <continue:0|1>: the tracked template keeps placeholders; real values go only
# into the temp copy that is pushed.
metadata() {
  python - "$JOBDIR/kernel-metadata.json" "$USER_NAME" "$SLUG" "${KAGGLE_DATASET:-}" "$1" "$ATTACH" <<'EOF'
import json, sys
path, user, slug, dataset, cont, attach = sys.argv[1:]
m = json.load(open(path))
m["id"] = f"{user}/{slug}"
m["title"] = slug
m["dataset_sources"] = [dataset] if dataset else []
m["kernel_sources"] = ([f"{user}/{slug}"] if cont == "1" else []) + [f"{user}/{s}" for s in attach.split()]
print(json.dumps(m, indent=2))
EOF
}

# Results only: training state (resume.pt, checkpoints) also sits in the session output
# (for --continue) and must not be pulled to E:. The listing is paginated, so ask for the
# largest page. No "/" in the pattern: Git Bash rewrites any argument containing one as a
# path, turning "(^|/)" into "(^|C:/Program Files/Git/)" and every "\." into "/.".
RESULTS="^(verdict\\.json|stages\\.jsonl|${ARTIFACT//./\\.})\$|\\.log\$"

case "${1:-}" in
check)
  echo "Kaggle user: $USER_NAME  job: $JOB ($SLUG)"
  kg kernels list --mine --page-size 5 && echo "OK: signed in and the API answers"
  ;;
push)
  CONT=0; [ "${2:-}" = --continue ] && CONT=1
  preflight
  SHA=$(git -C "$REPO" rev-parse HEAD)
  TMP=$(mktemp -d)
  notebook "$SHA" $CONT > "$TMP/$SLUG.ipynb"
  metadata $CONT > "$TMP/kernel-metadata.json"
  python -c "import json,sys; f=json.load(open(sys.argv[1]))['code_file']; sys.exit(0 if f == sys.argv[2] else f'code_file {f} != {sys.argv[2]}')"     "$TMP/kernel-metadata.json" "$SLUG.ipynb"
  kg kernels push -p "$TMP"
  rm -rf "$TMP"
  echo "Started $JOB at ${SHA:0:7}$([ $CONT = 1 ] && echo ', continuing from the previous version')."
  echo "Watch: bash push.sh $JOB status  |  web: https://www.kaggle.com/code/$USER_NAME/$SLUG"
  ;;
status) kg kernels status "$USER_NAME/$SLUG" ;;
fetch)
  # outputs go next to the job on E: (git-ignored), never to a C: download folder
  rm -rf "$JOBDIR/output"; mkdir -p "$JOBDIR/output"
  kg kernels output "$USER_NAME/$SLUG" -p "$JOBDIR/output" --force \
    --file-pattern "$RESULTS" --page-size 200
  # A download that "succeeds" with empty or missing files is a failure (T2 run 1).
  python - "$JOBDIR/output" "$ARTIFACT" <<'EOF'
import json, sys
from pathlib import Path
out, artifact = Path(sys.argv[1]), sys.argv[2]
problems = [f"{p.relative_to(out)} is empty" for p in out.rglob("*") if p.is_file() and p.stat().st_size == 0]
if not (out / artifact).is_file():
    problems.append(f"{artifact} missing")
try:
    v = json.loads((out / "verdict.json").read_text())
except (OSError, ValueError) as exc:
    v, problems = None, problems + [f"verdict.json unusable: {exc}"]
if v:
    print(f"verdict: {'PASSED' if v['passed'] else 'FAILED'}")
    for c in v["checks"]:
        print(f"  {'PASS' if c['ok'] else 'FAIL'}  {c['check']:<50} {c['detail']}")
    for key in ("resume_comparison", "summary"):
        if v.get(key):
            print(f"  info  {key}: {json.dumps(v[key])}")
for p in problems:
    print(f"FETCH PROBLEM: {p}")
sys.exit(1 if problems or not (v and v["passed"]) else 0)
EOF
  ;;
*) echo "usage: bash push.sh login | <job> check|push [--continue]|status|fetch"; exit 2 ;;
esac
