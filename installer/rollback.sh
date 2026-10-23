#!/system/bin/sh
STATE=/data/adb/pixel_launcher_compat_state
[ -f "$STATE/committed" ] || exit 0
. "$STATE/android_state.sh"

# Never restore HOME while the Pixel Recents overlay is still active. Its removal
# takes a reboot; restoring early revokes recents-only permissions from the stock HOME.
for attempt in $(seq 1 120); do
  [ "$(getprop sys.boot_completed)" = 1 ] && break
  sleep 2
done
[ "$(getprop sys.boot_completed)" = 1 ] || exit 1
CURRENT_RECENTS=$(android_call cmd overlay lookup android android:string/config_recentsComponentName) || exit 1
case "$CURRENT_RECENTS" in com.google.android.apps.nexuslauncher/*) exit 1 ;; esac

FAILED=0
HOME_ROLE=$(cat "$STATE/home-role-before")
HOME_COMPONENT=$(cat "$STATE/home-component-before")
valid_package "$HOME_ROLE" || exit 1
android_call cmd role add-role-holder --user 0 android.app.role.HOME "$HOME_ROLE" 0 || FAILED=1
android_call cmd package set-home-activity --user 0 "$HOME_COMPONENT" || FAILED=1
ACTUAL=$(android_call cmd role get-role-holders --user 0 android.app.role.HOME | head -n 1)
[ "$ACTUAL" = "$HOME_ROLE" ] || FAILED=1

if [ "$(cat "$STATE/hook-before")" = absent ]; then
  if android_call pm path "$HOOK" | grep -q '^package:'; then
    [ -x "$CLI" ] && android_call "$CLI" modules disable "$HOOK"
    [ -x "$CLI" ] && android_call "$CLI" scope set "$HOOK"
    android_call pm uninstall "$HOOK" || FAILED=1
  fi
else
  # Package version was reused, not overwritten, so only restore its scope/state.
  SCOPES=$(cat "$STATE/hook-scope-before")
  # Each token is strictly validated before passing it as a CLI argument.
  for SCOPE in $SCOPES; do
    PKG=${SCOPE%/*}; USER_ID=${SCOPE##*/}
    case "$PKG" in system|android) ;; *) valid_package "$PKG" || exit 1 ;; esac
    echo "$USER_ID" | grep -qE '^[0-9]+$' || exit 1
  done
  android_call "$CLI" scope set "$HOOK" $SCOPES || FAILED=1
  case "$(cat "$STATE/hook-enabled-before")" in
    enabled) android_call "$CLI" modules enable "$HOOK" || FAILED=1 ;;
    disabled) android_call "$CLI" modules disable "$HOOK" || FAILED=1 ;;
    *) FAILED=1 ;;
  esac
fi

while IFS= read -r PKG; do
  [ -n "$PKG" ] || continue
  valid_package "$PKG" || exit 1
  # Newly systemless-installed apps may already have vanished at package scan.
  if android_call pm path "$PKG" | grep -q '^package:'; then
    android_call pm uninstall "$PKG" || FAILED=1
  fi
done < "$STATE/owned-packages"

if [ "$FAILED" = 0 ]; then
  journal rollback completed
  # These exact paths contain only this module's state and one-shot rollback code.
  rm -f /data/adb/service.d/pixel_launcher_compat_restore.sh
  rm -rf /data/adb/pixel_launcher_compat_state
else
  journal rollback retry-required
  # Keep the baseline and one-shot helper for the next boot / explicit retry.
  exit 1
fi
