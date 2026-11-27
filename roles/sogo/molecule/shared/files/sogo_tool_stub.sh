#!/bin/sh
# Stand-in for sogo-tool in the restore tests: fails the way the mode in
# /etc/molecule-sogo-tool-mode says (backup-137, backup-1, backup-255-error,
# restore-notfound-error, restore-mixed); the backup of the restore-* modes
# finds nothing to save.
mode=$(cat /etc/molecule-sogo-tool-mode)
eval "user=\${$#}"
case "$1:$mode" in
  backup:backup-137) exit 137 ;;
  backup:backup-1) echo "molecule: backup failed" >&2; exit 1 ;;
  backup:backup-255-error)
    echo "ERROR: could not open channel to sogo@127.0.0.1" >&2; exit 255 ;;
  backup:restore-*) exit 255 ;;
  restore:restore-notfound-error)
    echo "user 'alice@example.com' not found" >&2
    echo "ERROR: could not open channel to postfixadmin@127.0.0.1" >&2
    exit 1 ;;
  # errors@example.com is unknown, every other user fails for real
  restore:restore-mixed)
    if [ "$user" = errors@example.com ]; then
      echo "user 'errors@example.com' not found" >&2
    else
      echo "ERROR: could not open channel to sogo@127.0.0.1" >&2
    fi
    exit 1 ;;
esac
echo "molecule-sogo-tool-stub: unexpected call $*" >&2
exit 2
