#!/usr/bin/env bash
# Resync the Song Factory library to https://yfevents.yakimafinds.com/music
# (and optionally the Fresh Hop page + Drive folder).
#
#   music-resync            # /music only
#   music-resync --dry-run  # show what would be published, change nothing
#   music-resync --all      # /music + /freshhop + Drive FreshHop folder
#
# Runs on hairydel. Needs ssh access to backoffice (content goes to
# ~/yakima/data + ~/yakima/uploads there; no rebuild or restart needed).
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
LOG="$HOME/.songfactory/logs/music-resync.log"
mkdir -p "$(dirname "$LOG")"

case "${1:-}" in
  --dry-run) exec python3 scripts/export_music_site.py --dry-run ;;
  --all)     ALL=1 ;;
  "")        ALL=0 ;;
  *) echo "usage: music-resync [--dry-run|--all]"; exit 2 ;;
esac

{
  echo "=== $(date '+%F %T') music-resync ${1:-}"
  python3 scripts/export_music_site.py | tail -1
  if [ "$ALL" = 1 ]; then
    python3 scripts/export_tag_to_drive.py --web | grep -E "Web page|removed|Done"
  fi
} 2>&1 | tee -a "$LOG"

code=$(curl -s -o /dev/null -w "%{http_code}" https://yfevents.yakimafinds.com/music)
echo "Live check: https://yfevents.yakimafinds.com/music -> HTTP $code" | tee -a "$LOG"
[ "$code" = 200 ]
