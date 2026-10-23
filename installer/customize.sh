#!/system/bin/sh
SKIPUNZIP=0
. "$MODPATH/android_state.sh"
ui_print '- Pixel Launcher Compatibility 0.5: verified, Android-aware payload'
[ "$BOOTMODE" = true ] || abort 'Install from the root manager in booted Android.'
[ -x "$CLI" ] || abort 'Active Vector with its CLI is required.'
[ "$(id -u)" = 0 ] || abort 'Root is required.'
[ ! -f "$STATE/rollback-pending" ] || abort 'Finish the pending uninstall rollback before reinstalling.'
cd "$MODPATH" || abort 'Cannot access module directory.'
sha256sum -c SHA256SUMS || abort 'Payload verification failed; device unchanged.'
SDK_EXPECTED=$(sed -n 's/.*"android_sdk": \([0-9]*\).*/\1/p' release-lock.json | head -n 1)
ABI_EXPECTED=$(sed -n 's/.*"abi": "\([^"]*\)".*/\1/p' release-lock.json | head -n 1)
[ "$(getprop ro.build.version.sdk)" = "$SDK_EXPECTED" ] || abort 'Prepared ZIP is for a different Android API level; rebuild for this phone.'
[ "$(getprop ro.product.cpu.abi)" = "$ABI_EXPECTED" ] || abort 'Prepared ZIP is for a different CPU architecture.'
SYSUI_EXPECTED=$(sed -n 's/.*"systemui_sha256": "\([a-f0-9]*\)".*/\1/p' release-lock.json | head -n 1)
SYSUI_APK=$(android_call pm path com.android.systemui | sed -n 's/^package://p' | head -n 1)
[ "$(sha256sum "$SYSUI_APK" | cut -d ' ' -f1)" = "$SYSUI_EXPECTED" ] || abort 'SystemUI changed; rebuild and verify the compatibility profile.'

# Finish all conflict checks before baseline capture or APK installation.
TAB=$(printf '\t')
while IFS="$TAB" read -r PKG PREFIX DIGEST COMPONENT; do
  valid_package "$PKG" || abort 'Invalid component package.'
  case "$PREFIX" in system/priv-app/PixelLauncherCompat/|system/priv-app/PixelCompat_*/) ;; *) abort 'Invalid payload path.' ;; esac
  case "$PREFIX" in *..*) abort 'Unsafe payload path.' ;; esac
  EXISTING=$(android_call pm path "$PKG" | sed -n 's/^package://p' | head -n 1)
  if [ "$COMPONENT" = launcher ] && [ -n "$EXISTING" ]; then
    BUNDLED=$(find "$MODPATH/$PREFIX" -name '*.apk' | head -n 1)
    [ "$(sha256sum "$EXISTING" | cut -d ' ' -f1)" = "$(sha256sum "$BUNDLED" | cut -d ' ' -f1)" ] || abort 'Pre-existing launcher differs; updating existing app data is not reversible yet.'
  fi
done < components.tsv

HOOK_OLD=$(android_call pm path "$HOOK" | sed -n 's/^package://p' | head -n 1)
HOOK_NEW="$MODPATH/hook/PixelLauncherCompatHook.apk"
LEGACY=$(sed -n 's/^version=//p' /data/adb/modules/pixel_launcher_compat/module.prop 2>/dev/null)
if [ -n "$HOOK_OLD" ]; then
  OLD_SHA=$(sha256sum "$HOOK_OLD" | cut -d ' ' -f1)
  NEW_SHA=$(sha256sum "$HOOK_NEW" | cut -d ' ' -f1)
  if [ "$OLD_SHA" != "$NEW_SHA" ] && [ -f "$STATE/committed" ] && [ "$(cat "$STATE/hook-before")" = present ]; then
    abort 'Cannot update a pre-existing companion hook: preserving its original APK and data.'
  fi
  # Never replace a hook app installed outside this module with another binary.
  if [ "$OLD_SHA" != "$NEW_SHA" ] && [ ! -f "$STATE/committed" ]; then
    case "$LEGACY" in 0.1.0|0.2.0|0.3.0|0.4.0) ;; *) abort 'Pre-existing companion hook differs; refusing to overwrite it.' ;; esac
  fi
fi

capture_baseline || abort 'Cannot capture rollback baseline; no APKs installed.'
arm_rollback || abort 'Cannot arm rollback helper; no APKs installed.'
FAILED=1
on_exit() {
  [ "$FAILED" = 0 ] && return
  journal installation failed
  # During an upgrade keep the current module and hook functioning. Baseline survives
  # for a retry. On a clean install, an unowned new helper is removed immediately.
  if [ ! -f /data/adb/modules/pixel_launcher_compat/module.prop ]; then
    schedule_rollback
    /system/bin/sh "$STATE/rollback.sh"
  fi
}
trap on_exit EXIT

while IFS="$TAB" read -r PKG PREFIX DIGEST COMPONENT; do
  record_package "$PKG" || abort 'Cannot record component ownership.'
  if [ "$COMPONENT" != launcher ] && grep -qxF "$PKG" "$STATE/preexisting-packages"; then
    ui_print "- Reusing pre-existing $PKG; it will not be updated or removed"
    rm -rf "$MODPATH/$PREFIX"
  fi
done < components.tsv

# One combined permission file, with only requested privileged permissions that
# actually exist in this ROM. No blind signature-only grants.
PERMISSION_DUMP=$(android_call dumpsys package permissions)
printf '%s\n' "$PERMISSION_DUMP" | awk '
  /Permission \[/ { name=$2; gsub(/\[/,"",name); gsub(/\]/,"",name) }
  /prot=/ && /privileged/ { print name }
' | sort -u > "$MODPATH/rom-privileged.txt"
mkdir -p "$MODPATH/system/etc/permissions"
XML="$MODPATH/system/etc/permissions/privapp-permissions-pixel-launcher-compat.xml"
printf '%s\n' '<?xml version="1.0" encoding="utf-8"?>' '<permissions>' > "$XML"
while IFS="$TAB" read -r PKG PREFIX DIGEST COMPONENT; do
  [ -d "$MODPATH/$PREFIX" ] || continue
  printf '  <privapp-permissions package="%s">\n' "$PKG" >> "$XML"
  while IFS= read -r PERM; do
    if grep -qxF "$PERM" "$MODPATH/rom-privileged.txt"; then
      printf '    <permission name="%s" />\n' "$PERM" >> "$XML"
    fi
  done < "$MODPATH/permissions/$PKG.txt"
  printf '%s\n' '  </privapp-permissions>' >> "$XML"
done < components.tsv
printf '%s\n' '</permissions>' >> "$XML"

if [ -z "$HOOK_OLD" ] || [ "$OLD_SHA" != "$NEW_SHA" ]; then
  STAGE="/data/local/tmp/pixel-launcher-compat-hook-$$.apk"
  cp "$HOOK_NEW" "$STAGE" || abort 'Cannot stage companion hook.'
  chmod 0644 "$STAGE"
  chcon u:object_r:shell_data_file:s0 "$STAGE"
  android_call su -M -c "pm install -r '$STAGE'"
  RESULT=$?
  rm -f "$STAGE"
  [ "$RESULT" = 0 ] || abort 'Companion installation failed.'
  journal hook installed
fi
android_call su -M -c "$CLI scope set $HOOK com.google.android.apps.nexuslauncher/0" || abort 'Cannot set hook scope.'
android_call su -M -c "$CLI modules enable $HOOK" || abort 'Cannot enable hook.'
journal hook scoped
# Replacing a systemless APK can preserve its folder timestamp. Discard only
# this launcher's parsed-package cache so an older APK path cannot mask its
# privileged system copy after an uninstall/reinstall cycle. App data is kept.
if [ -d /data/system/package_cache ]; then
  find /data/system/package_cache -type f -name 'PixelLauncherCompat-*' -exec rm -f {} \;
fi
set_perm_recursive "$MODPATH" 0 0 0755 0644
for SCRIPT in action.sh service.sh uninstall.sh rollback.sh android_state.sh; do
  set_perm "$MODPATH/$SCRIPT" 0 0 0755
done
FAILED=0
trap - EXIT
journal installation staged
ui_print '- Installation staged. Reboot to activate systemless components.'
ui_print '- Root-manager uninstall + reboot restores the saved HOME and removes owned additions.'
ui_print '- Optional feature availability is reported separately; APK presence is not a feature test.'
