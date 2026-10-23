#!/system/bin/sh
MODDIR=${0%/*}
STATE=/data/adb/pixel_launcher_compat_state
[ -f "$STATE/android_state.sh" ] || exit 1
. "$STATE/android_state.sh"
# Pixel is now the Recents provider. The ROM's Quickstep HOME may depend on
# recents-only permissions, so select Pixel as soon as PackageManager is ready,
# before waiting for boot_completed (which may itself wait for a working HOME).
HOME_READY=0
for attempt in $(seq 1 120); do
  if [ -n "$(pm path com.google.android.apps.nexuslauncher 2>/dev/null)" ]; then
    HOME_RESULT=$(cmd package set-home-activity --user 0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity 2>&1)
    CURRENT_HOME=$(cmd role get-role-holders --user 0 android.app.role.HOME 2>/dev/null | head -n 1)
    if [ "$CURRENT_HOME" = com.google.android.apps.nexuslauncher ]; then
      journal home selected-pixel
      HOME_READY=1
      break
    fi
  fi
  sleep 2
done
[ "$HOME_READY" = 1 ] || exit 1
for attempt in $(seq 1 120); do
  [ "$(getprop sys.boot_completed)" = 1 ] && break
  sleep 2
done
[ "$(getprop sys.boot_completed)" = 1 ] || exit 1
[ -f "$STATE/committed" ] || exit 1
capture() {
  RESULT=$("$@" 2>&1)
  printf '%s\n' "$RESULT"
}
# Runtime-dangerous permissions are not granted automatically here.
# Report installed components/services; do not confuse installation with support.
{
  printf 'Pixel Launcher Compatibility component status\n'
  date
  TAB=$(printf '\t')
  while IFS="$TAB" read -r PKG PREFIX DIGEST COMPONENT; do
    printf '\n[%s] %s\n' "$COMPONENT" "$PKG"
    capture pm path "$PKG"
  done < "$MODDIR/components.tsv"
  printf '\nRelevant ROM services:\n'
  capture service list | grep -iE 'search_ui|smartspace|app_prediction|content_suggestions'
} > "$STATE/component-status.txt" 2>&1
