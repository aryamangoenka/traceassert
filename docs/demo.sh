#!/usr/bin/env bash
# re-renders docs/demo.gif from a real run. run from the repo root.
#
# run-01 is a published, redacted trace from the experiment, so nothing
# personal lands in the gif. routing is on if a .env with JEV_API_KEY exists,
# otherwise the routed claims just read "routing not configured", which is
# also a fine thing to show.
#
# needs: brew install asciinema agg
# (vhs was the first attempt, it renders through a headless browser and died
# silently on this machine, asciinema records the pty directly, agg
# rasterizes the cast, no browser anywhere)
set -euo pipefail

# the typing is cosmetic so the gif has some motion in it. the command shown is
# the command run and the output is untouched, traceassert really does print
# the whole receipt in one go.
typed=$(mktemp)
cat > "$typed" <<'EOF'
cmd="traceassert check experiment/runs/run-01/trace.jsonl"
printf '$ '
for ((i = 0; i < ${#cmd}; i++)); do printf '%s' "${cmd:$i:1}"; sleep 0.035; done
printf '\n'
sleep 0.6
uv run traceassert check experiment/runs/run-01/trace.jsonl
EOF

asciinema rec --headless --window-size 136x44 --overwrite -q \
  -c "bash $typed" docs/demo.cast
rm -f "$typed"

agg --cols 136 --rows 44 --font-size 15 --theme monokai \
  --idle-time-limit 1.5 --last-frame-duration 6 \
  docs/demo.cast docs/demo.gif

ls -la docs/demo.gif
