from pathlib import Path
import hashlib
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
MOD = ROOT / 'module'
APK = ROOT / 'pixel-launcher-original.apk'
DIGEST = hashlib.sha256(APK.read_bytes()).hexdigest()
SYSUI_DIGEST = hashlib.sha256((ROOT / 'SystemUI.apk').read_bytes()).hexdigest()

def write(name, value):
    path = MOD / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.replace('\r\n', '\n'), encoding='utf-8', newline='\n')

package_dump = (ROOT / 'package-device.txt').read_text(encoding='utf-8-sig')
requested = package_dump.split('requested permissions:', 1)[1].split('install permissions:', 1)[0]
permissions = sorted(set(re.findall(r'^\s+([\w.]+)\s*$', requested, re.M)))
assert len(permissions) > 40, 'Missing requested permission metadata'
write('requested-permissions.txt', '\n'.join(permissions) + '\n')
write('module.prop', '''id=pixel_launcher_compat
name=Pixel Launcher Compatibility (Android 16) - Experimental
version=0.4.0
versionCode=4
author=Henry / Codex
description=Pixel Launcher 16 v907 compatibility for the tested onyx Android 16 ROM: privileges, Pixel Recents, scoped automation/search/TaskInfo/overview adapters. Requires active Vector.
''')
write('system/etc/sysconfig/pixel-launcher-compat.xml', '''<?xml version="1.0" encoding="utf-8"?>
<config>
    <hidden-api-whitelisted-app package="com.google.android.apps.nexuslauncher" />
</config>
''')
dest = MOD / 'system/priv-app/PixelLauncherCompat/PixelLauncher.apk'
dest.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(APK, dest)
overlay = ROOT / 'recents-overlay/signed/recents-aligned-debugSigned.apk'
old_overlay = MOD / 'system/overlay/PixelLauncherRecentsCompat/PixelLauncherRecentsCompat.apk'
if old_overlay.exists():
    old_overlay.unlink()
overlay_dest = MOD / 'system/product/overlay/PixelLauncherRecentsCompat/PixelLauncherRecentsCompat.apk'
overlay_dest.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(overlay, overlay_dest)
hook_dest = MOD / 'hook/PixelLauncherCompatHook.apk'
hook_dest.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(ROOT / 'hook/signed/hook-aligned-debugSigned.apk', hook_dest)
write('customize.sh', '''#!/system/bin/sh
SKIPUNZIP=0
PKG=com.google.android.apps.nexuslauncher
ui_print "- Pixel Launcher compatibility 0.4.0 (experimental)"
[ "$BOOTMODE" = true ] || abort "Install from your root manager in booted Android, not recovery."
VECTOR_CLI=/data/adb/lspd/cli
[ -x "$VECTOR_CLI" ] || abort "Active Vector framework with CLI is required for the scoped compatibility hook."
"$VECTOR_CLI" status > "$MODPATH/vector-status.txt" 2>&1 || abort "Vector framework is not available."
SDK_NOW=$(getprop ro.build.version.sdk)
[ "$SDK_NOW" -ge 36 ] 2>/dev/null || abort "Android 16 / API 36 or later required."
[ "$(getprop ro.product.cpu.abi)" = arm64-v8a ] || abort "This APK build requires arm64-v8a."
SYSUI_APK=$(pm path com.android.systemui | sed -n 's/^package://p' | head -n 1)
SYSUI_SHA=$(sha256sum "$SYSUI_APK" | cut -d ' ' -f1)
[ "$SYSUI_SHA" = __SYSUI_SHA__ ] || abort "SystemUI differs from the tested ROM. This build's legacy overview adapter requires a ROM-specific interface check."
[ "$SDK_NOW" = 36 ] || ui_print "! Newer Android version: compatibility is unverified."
EXPECTED_SHA=__SHA__
APK="$MODPATH/system/priv-app/PixelLauncherCompat/PixelLauncher.apk"
ACTUAL_SHA=$(sha256sum "$APK" | cut -d ' ' -f1)
[ "$ACTUAL_SHA" = "$EXPECTED_SHA" ] || abort "Bundled APK checksum mismatch."
# Do not replace a different preinstalled launcher or silently change signing identities.
if pm list packages -s | grep -qx "package:$PKG"; then
  [ -f /data/adb/modules/pixel_launcher_compat/module.prop ] || abort "ROM already includes Pixel Launcher. Disable conflicting modules or use a ROM-specific build."
fi
EXISTING=$(pm path "$PKG" | sed -n 's/^package://p' | head -n 1)
if [ -n "$EXISTING" ]; then
  EXISTING_SHA=$(sha256sum "$EXISTING" | cut -d ' ' -f1)
  [ "$EXISTING_SHA" = "$EXPECTED_SHA" ] || abort "Installed APK differs from v907 source. Keep your data; rebuild for that APK first."
fi
mkdir -p "$MODPATH/system/etc/permissions"
dumpsys package permissions > "$MODPATH/permissions-snapshot.txt"
[ -s "$MODPATH/permissions-snapshot.txt" ] || abort "Unable to inspect ROM permissions."
# Generate only permissions declared privileged by this ROM AND requested by this APK.
# Pure signature permissions cannot be granted with a privapp XML.
awk '
  /Permission \\[/ { name=$2; gsub(/\\[/,"",name); gsub(/\\]/,"",name) }
  /prot=/ && /privileged/ { print name }
' "$MODPATH/permissions-snapshot.txt" | sort -u > "$MODPATH/rom-privileged.txt"
XML="$MODPATH/system/etc/permissions/privapp-permissions-pixel-launcher-compat.xml"
printf '%s\\n' '<?xml version="1.0" encoding="utf-8"?>' '<permissions>' "  <privapp-permissions package=\\"$PKG\\">" > "$XML"
COUNT=0
while IFS= read -r PERM; do
  if grep -qxF "$PERM" "$MODPATH/rom-privileged.txt"; then
    printf '    <permission name="%s" />\\n' "$PERM" >> "$XML"
    COUNT=$((COUNT + 1))
  fi
done < "$MODPATH/requested-permissions.txt"
printf '%s\\n' '  </privapp-permissions>' '</permissions>' >> "$XML"
[ "$COUNT" -gt 0 ] || abort "No privileged permissions detected; permission inspection failed."
ui_print "- Installing scoped compatibility hook"
HOOK_APK="$MODPATH/hook/PixelLauncherCompatHook.apk"
HOOK_STAGE="/data/local/tmp/pixel-launcher-compat-hook-$$.apk"
cp "$HOOK_APK" "$HOOK_STAGE" || abort "Cannot stage companion APK."
chmod 0644 "$HOOK_STAGE"
chcon u:object_r:shell_data_file:s0 "$HOOK_STAGE"
su -M -c "pm install -r '$HOOK_STAGE'"
HOOK_RESULT=$?
rm -f "$HOOK_STAGE"
[ "$HOOK_RESULT" = 0 ] || abort "Hook APK installation failed."
su -M -c "$VECTOR_CLI scope set dev.henry.pixellauncher.compat com.google.android.apps.nexuslauncher/0" || abort "Could not configure hook scope."
su -M -c "$VECTOR_CLI modules enable dev.henry.pixellauncher.compat" || abort "Could not enable compatibility hook."
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/action.sh" 0 0 0755
ui_print "- Allowlisted $COUNT requested privileged permissions for this ROM"
ui_print "- Original APK retained, no resigning or data clearing"
ui_print "- Optional computer-control integration disabled inside Pixel Launcher"
ui_print "- Stock HOME remains selected; Recents switches to Pixel Launcher"
ui_print "- Reboot, then open Pixel Launcher to test"
ui_print "- KernelSU/APatch require working system-file mounting support"
'''.replace('__SHA__', DIGEST).replace('__SYSUI_SHA__', SYSUI_DIGEST))
write('action.sh', '''#!/system/bin/sh
MODDIR=${0%/*}
OUT=/sdcard/Download/pixel-launcher-compat-diagnostics.txt
mkdir -p /sdcard/Download
{
  echo "Pixel Launcher Compatibility diagnostics"
  date
  getprop ro.build.version.sdk
  getprop ro.build.display.id
  echo "Module-mounted APK:"
  ls -l /system/priv-app/PixelLauncherCompat/PixelLauncher.apk
  echo "Current HOME:"
  cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME
  echo "Launcher package:"
  dumpsys package com.google.android.apps.nexuslauncher
  echo "Recent Java crash log:"
  logcat -d -b crash -t 150 AndroidRuntime:E '*:S'
} > "$OUT" 2>&1
echo "Saved $OUT"
echo "Review this file before sharing: it can contain other app crash information."
''')
write('uninstall.sh', '''#!/system/bin/sh
# Remove only this module's companion hook and its Vector configuration.
if [ -x /data/adb/lspd/cli ]; then
  /data/adb/lspd/cli modules disable dev.henry.pixellauncher.compat
  /data/adb/lspd/cli scope set dev.henry.pixellauncher.compat
fi
pm uninstall dev.henry.pixellauncher.compat
''')
write('META-INF/com/google/android/updater-script', '#MAGISK\n')
installer = (ROOT / 'tools/module_installer.sh').read_text(encoding='utf-8')
write('META-INF/com/google/android/update-binary', installer)
write('README.md', '''# Pixel Launcher Compatibility 0.4.0 — experimental

Built for the original Pixel Launcher 16 / versionCode 907 extracted from Henry's phone.
Android 16 API 36, arm64. Later APIs are allowed with a warning but untested.
This build checks the SystemUI APK hash and refuses unverified ROM interfaces.
It is a working candidate for the tested ROM, not a universal Android 16+ release.

## What it does

- Mounts the unchanged, originally signed APK under /system/priv-app.
- Adds a hidden-api-whitelisted-app entry for this package only.
- Generates a privileged-permission XML using the target ROM's declared protection levels.
- Preserves existing app data, stock launcher, and HOME selection.
- Includes a static framework resource overlay selecting Pixel Launcher as Recents provider.
  This enables the ROM's recents-protected permissions, including INTERNAL_SYSTEM_WINDOW.
- Installs a companion Vector hook scoped only to com.google.android.apps.nexuslauncher.
  The hook supplies null ComputerControlExtensions to AutomationRepositoryImpl, which uses
  its existing optional-dependency fallback to skip computer-control listener registration.
  This avoids the ROM's role-permission crash without granting new role-management powers.
- Skips device-search session setup only when SearchUiManager is absent. Local app search remains.
- Rebuilds task metadata on frameworks missing isRealActivityAppLockEnabled, using the
  ROM's isTopAppLocked field and retaining split-screen capability, colors, bounds and locked state.
- Sends legacy overview-shown notification as transaction 7 rather than the APK's incompatible
  transaction 62. Suppresses overview-hidden notification, which collides with this ROM's
  force-stop transaction 63. This adapter is specific to the verified SystemUI interface.
- Makes no framework modifications, device spoofing, global hidden API changes, SELinux changes,
  signature-verification bypasses, automatic reboots, or permanent partition writes.

## Installation

1. Keep the ROM launcher installed and selected for the first boot.
2. Requires an active Vector framework with /data/adb/lspd/cli. Installer sets the hook
   scope and enables it automatically. This is not a standalone module without Vector.
   Install through your root manager while Android is running, then reboot.
   KernelSU/APatch compatibility depends on system-file mounting support in that setup
   (for KernelSU versions using metamodules, an appropriate mounting metamodule is required).
   Recovery flashing and adb sideload are not supported.
3. Open Pixel Launcher explicitly to test before selecting it in Default apps > Home app.
4. If it crashes, use the module Action button, or run its action.sh as root, and inspect
   Download/pixel-launcher-compat-diagnostics.txt.

Do not uninstall your current Pixel Launcher first. The installer checks that any existing
copy exactly matches the bundled APK; other APK builds require rebuilding this package.
Do not combine with other Pixel Launcher/QuickSwitch/systemizer modules.

## Rollback

Select the ROM launcher as HOME before disabling or removing this module, then reboot.
Existing /data app and launcher data remain. Removal also disables and uninstalls the
companion hook; disabling alone leaves the companion installed. The hook can be disabled
separately in Vector. Removing this module restores the ROM's Recents provider at reboot.
If Android cannot finish booting, use root-capable recovery to create:
/data/adb/modules/pixel_launcher_compat/disable
Then reboot. Magisk's documented safe-mode procedure is another recovery option.

## Limits and validation

This is an initial compatibility candidate, not a universal Pixel Launcher port.
Device-tested on Henry's onyx Android 16 / API 36 ROM with KernelSU + NoMount.
The module installs and the phone boots. System placement and package exemption remove
the InteractionJankMonitor crash. The product Recents overlay grants the recents-protected
permissions and removes the INTERNAL_SYSTEM_WINDOW crash.
The companion hook removes the subsequent role-permission, absent SearchUiManager,
TaskInfo app-lock field, and overview notification incompatibilities. Interactive tests
passed for HOME, app drawer, Calculator launch, local app search, and Recents cards.
Launcher and SystemUI process IDs remained stable and a fresh Java crash log was empty
during the final interaction sequence. DEVICE-TEST.md beside the ZIP records the evidence.
Three-button navigation was tested; gesture-navigation mode, widgets, split screen,
work profiles, Pixel services, and long-term stability remain unverified.

System placement and allowlists cannot grant pure platform-signature permissions.
Recents and gesture integration now use a framework resource overlay and require device testing.
Disabling the module and rebooting restores the ROM's Recents provider. Pixel-only services,
Smartspace, search, wallpaper integration, and later framework changes may need further work.
If an API truly does not exist in another ROM, an allowlist cannot recreate it.

## Sources

- https://topjohnwu.github.io/Magisk/guides.html
- https://topjohnwu.github.io/Magisk/faq.html
- https://github.com/aosp-mirror/platform_frameworks_base/blob/master/core/java/android/content/pm/ApplicationInfo.java
- https://github.com/aosp-mirror/platform_frameworks_base/blob/master/services/core/java/com/android/server/SystemConfig.java
- https://github.com/JingMatrix/Vector
- https://api.xposed.info/reference/de/robv/android/xposed/XposedBridge.html

For personal testing with the APK already owned on the connected device. Do not assume
permission to publicly redistribute Google's APK. Build source is build_module.py beside the ZIP.
''')
for path in MOD.rglob('*.xml'):
    ET.parse(path)
assert hashlib.sha256(dest.read_bytes()).hexdigest() == DIGEST
out = ROOT / 'PixelLauncher-Compat-v0.4.0-experimental.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(MOD.rglob('*')):
        if path.is_file():
            info = zipfile.ZipInfo(path.relative_to(MOD).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if path.name.endswith('.sh') or path.name == 'update-binary' else 0o644
            info.external_attr = (0o100000 | mode) << 16
            archive.writestr(info, path.read_bytes())
with zipfile.ZipFile(out) as archive:
    assert archive.testzip() is None
print(f'Built {out} ({out.stat().st_size:,} bytes)')
print(f'Original APK SHA256: {DIGEST}')
