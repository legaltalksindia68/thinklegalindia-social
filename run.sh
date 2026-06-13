#!/usr/bin/env bash
# Scheduled entrypoint for the Think Legal India social pipeline.
# Generates the next post and posts it via the Make webhook (live).
# Honours automation/PAUSED (created => skips). Preflight in pipeline.py
# also refuses if the Make scenario is inactive or has a queued bundle.
#
# Logs to outputs/cron.log (rolled inside the file by date).
set -e
cd "$(dirname "$0")"

PY=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
[ -x "$PY" ] || PY=$(/usr/bin/env which python3)

mkdir -p outputs
echo "===== $(date) =====" >> outputs/cron.log
"$PY" pipeline.py --live >> outputs/cron.log 2>&1
