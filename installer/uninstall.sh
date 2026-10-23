#!/system/bin/sh
STATE=/data/adb/pixel_launcher_compat_state
if [ -f "$STATE/android_state.sh" ]; then
  . "$STATE/android_state.sh"
  schedule_rollback
fi
# The durable service.d helper completes cleanup after this module's Recents overlay
# has been unmounted at reboot. Do not remove pre-existing APKs or restore HOME early.
