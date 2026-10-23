#!/system/bin/sh
MODDIR=${0%/*}
OUT=/sdcard/Download/pixel-launcher-compat-diagnostics.txt
mkdir -p /sdcard/Download
capture() {
  RESULT=$("$@" 2>&1)
  printf '%s\n' "$RESULT"
}
{
  echo 'Pixel Launcher Compatibility diagnostics'
  date
  cat "$MODDIR/module.prop"
  cat "$MODDIR/release-lock.json"
  echo 'Current HOME and Recents'
  capture cmd role get-role-holders --user 0 android.app.role.HOME
  capture cmd overlay lookup android android:string/config_recentsComponentName
  echo 'Components and services'
  cat /data/adb/pixel_launcher_compat_state/component-status.txt
  capture service list
  capture dumpsys package com.google.android.apps.nexuslauncher
  capture logcat -d -b crash -t 100 AndroidRuntime:E '*:S'
} > "$OUT" 2>&1
echo "Saved $OUT; review before sharing because other app crashes may be included."
