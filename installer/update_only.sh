#!/system/bin/sh
SKIPUNZIP=1
ACTIVE=/data/adb/modules/pixel_launcher_compat
STATE=/data/adb/pixel_launcher_compat_state
[ "$BOOTMODE" = true ] || abort 'Install from the root manager in booted Android.'
[ "$MODPATH" != "$ACTIVE" ] || abort 'An isolated module staging directory is required.'
[ -f "$ACTIVE/module.prop" ] || abort 'Install a prepared full bundle first; this ZIP is an update only.'
[ ! -f "$ACTIVE/remove" ] && [ ! -f "$ACTIVE/disable" ] || abort 'Enable the existing module and reboot before updating.'
[ -f "$STATE/committed" ] && [ ! -f "$STATE/rollback-pending" ] || abort 'A committed, active uninstall baseline is required.'
grep -qx 'id=pixel_launcher_compat' "$ACTIVE/module.prop" || abort 'Wrong module identity.'
OLD_CODE=$(sed -n 's/^versionCode=//p' "$ACTIVE/module.prop")
case "$OLD_CODE" in 5|6) ;; *) abort 'Unsupported update source version; prepare a full ZIP.' ;; esac
[ "$(getprop ro.build.version.sdk)" = 36 ] || abort 'This update is for the tested Android 16 profile.'
[ "$(getprop ro.product.cpu.abi)" = arm64-v8a ] || abort 'This update is for arm64-v8a.'
[ "$(sha256sum "$ACTIVE/SHA256SUMS" | cut -d ' ' -f1)" = '@MANIFEST_SHA@' ] || abort 'Installed payload manifest is not the tested full bundle.'
[ "$(sha256sum "$ACTIVE/release-lock.json" | cut -d ' ' -f1)" = '@LOCK_SHA@' ] || abort 'Installed profile is not supported by this update.'
(cd "$ACTIVE" && sha256sum -c SHA256SUMS) || abort 'Installed payload failed integrity verification.'
# Preserve the known payload and rollback scripts, not root-manager flags or
# generated product/vendor symlinks. No APK install or baseline recapture occurs.
for ENTRY in system hook permissions components.tsv release-lock.json SHA256SUMS requested-permissions.txt rom-privileged.txt service.sh action.sh android_state.sh rollback.sh uninstall.sh customize.sh README.md; do
  [ -e "$ACTIVE/$ENTRY" ] || abort "Missing installed module entry: $ENTRY"
  cp -af "$ACTIVE/$ENTRY" "$MODPATH/" || abort "Cannot retain $ENTRY"
done
unzip -p "$ZIPFILE" module.prop > "$MODPATH/module.prop" || abort 'Cannot install new module metadata.'
set_perm_recursive "$MODPATH" 0 0 0755 0644
for SCRIPT in action.sh service.sh uninstall.sh rollback.sh android_state.sh; do
  set_perm "$MODPATH/$SCRIPT" 0 0 0755
done
ui_print '- Update URL enabled; verified payload and uninstall baseline retained.'
ui_print '- Reboot to activate the staged update.'
