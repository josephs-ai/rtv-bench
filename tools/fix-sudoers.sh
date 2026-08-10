#!/bin/bash
# Repairs /etc/sudoers.d/rtveval-netshape (broken by a line-wrapped paste).
# Run as: sudo bash ~/rtv-eval/tools/fix-sudoers.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "run with sudo: sudo bash $0" >&2
  exit 1
fi

TARGET=/etc/sudoers.d/rtveval-netshape
TMP=$(mktemp)
printf 'joseph ALL=(root) NOPASSWD: /usr/sbin/dnctl, /sbin/pfctl\n' > "$TMP"

# Never install an invalid sudoers file - validate first.
if ! visudo -cf "$TMP"; then
  rm -f "$TMP"
  echo "generated rule failed visudo validation - aborting, nothing changed" >&2
  exit 1
fi

install -m 440 -o root -g wheel "$TMP" "$TARGET"
rm -f "$TMP"
echo "installed $TARGET:"
cat "$TARGET"
echo
echo "verifying passwordless dnctl as joseph..."
if sudo -u joseph sudo -n dnctl list >/dev/null 2>&1; then
  echo "OK: joseph can run dnctl without a password"
else
  echo "NOTE: verification inconclusive from inside sudo - run 'sudo -n dnctl list' yourself"
fi
