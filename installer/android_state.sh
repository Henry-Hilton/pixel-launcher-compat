#!/system/bin/sh
# Shared transaction helpers. No global permission or signature bypasses.
STATE=/data/adb/pixel_launcher_compat_state
RESTORE_HELPER=/data/adb/service.d/pixel_launcher_compat_restore.sh
HOOK=dev.henry.pixellauncher.compat
CLI=/data/adb/lspd/cli

# Binder shell commands reject root-manager log file descriptors. Give both
# streams pipe descriptors, then relay output without changing the exit code.
android_call() {
  ANDROID_RESULT=$("$@" 2>&1)
  ANDROID_STATUS=$?
  printf '%s\n' "$ANDROID_RESULT"
  return "$ANDROID_STATUS"
}

valid_package() { echo "$1" | grep -qE '^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$'; }
write_atomic() { printf '%s\n' "$2" > "$1.tmp" && mv "$1.tmp" "$1"; }
journal() { printf '%s\t%s\t%s\n' "$(date +%s)" "$1" "$2" >> "$STATE/journal.tsv"; }

capture_baseline() {
  [ -f "$STATE/committed" ] && return 0
  [ ! -e "$STATE" ] || { echo 'Unfinished transaction exists; restore it before installing.'; return 1; }
  HOME_COMPONENT=$(android_call cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME | tail -n 1)
  HOME_ROLE=$(android_call cmd role get-role-holders --user 0 android.app.role.HOME | head -n 1)
  HOOK_BEFORE=absent
  HOOK_STATUS=
  SCOPES=
  MIGRATION=
  # Migrate only the known prototype created in this session. The original HOME is
  # documented in DEVICE-TEST.md; companion hook was introduced by that prototype.
  LEGACY=$(sed -n 's/^version=//p' /data/adb/modules/pixel_launcher_compat/module.prop 2>/dev/null)
  case "$LEGACY" in
    0.1.0|0.2.0|0.3.0|0.4.0)
      HOME_COMPONENT=com.android.launcher3/.uioverrides.QuickstepLauncher
      HOME_ROLE=com.android.launcher3
      MIGRATION=prototype-0.4-migration
      ;;
    *)
      if android_call pm path "$HOOK" | grep -q "^package:"; then
        HOOK_BEFORE=present
        HOOK_STATUS=$(android_call "$CLI" modules ls | awk -v p="$HOOK" '$1==p {print $3}')
        case "$HOOK_STATUS" in enabled|disabled) ;; *) echo 'Cannot capture hook state'; return 1 ;; esac
        SCOPES=$(android_call "$CLI" scope ls "$HOOK" | awk 'NR>2 && NF==2 {print $1 "/" $2}')
      fi
      ;;
  esac
  case "$HOME_COMPONENT" in *'/'*) ;; *) echo 'Cannot capture previous HOME'; return 1 ;; esac
  valid_package "$HOME_ROLE" || { echo 'Cannot capture previous HOME role'; return 1; }
  STAGE=/data/adb/pixel_launcher_compat_state.new
  # A stale staging directory cannot contain applied app changes: install starts
  # only after the committed baseline is atomically renamed into place.
  rm -rf "$STAGE"
  mkdir -p "$STAGE" || return 1
  chmod 0700 "$STAGE"
  printf '%s\n' "$HOME_COMPONENT" > "$STAGE/home-component-before" &&
  printf '%s\n' "$HOME_ROLE" > "$STAGE/home-role-before" &&
  printf '%s\n' "$HOOK_BEFORE" > "$STAGE/hook-before" &&
  printf '%s\n' "$HOOK_STATUS" > "$STAGE/hook-enabled-before" &&
  printf '%s\n' "$SCOPES" > "$STAGE/hook-scope-before" &&
  printf '%s\n' "$MIGRATION" > "$STAGE/migration" &&
  touch "$STAGE/owned-packages" "$STAGE/preexisting-packages" "$STAGE/journal.tsv" "$STAGE/committed" &&
  mv "$STAGE" "$STATE" || return 1
  journal baseline captured
}

record_package() {
  PKG=$1
  valid_package "$PKG" || return 1
  grep -qxF "$PKG" "$STATE/owned-packages" && return 0
  grep -qxF "$PKG" "$STATE/preexisting-packages" && return 0
  if [ -n "$(android_call pm path "$PKG")" ]; then
    printf '%s\n' "$PKG" >> "$STATE/preexisting-packages"
    journal reused "$PKG"
  else
    printf '%s\n' "$PKG" >> "$STATE/owned-packages"
    journal added "$PKG"
  fi
}

arm_rollback() {
  mkdir -p /data/adb/service.d
  cp "$MODPATH/rollback.sh" "$STATE/rollback.sh" || return 1
  cp "$MODPATH/android_state.sh" "$STATE/android_state.sh" || return 1
  cat > "$RESTORE_HELPER" <<'EOF'
#!/system/bin/sh
# A pending rollback continues after module overlays are gone and Android is ready.
STATE=/data/adb/pixel_launcher_compat_state
if [ -f "$STATE/rollback-pending" ]; then
  /system/bin/sh "$STATE/rollback.sh"
fi
EOF
  chmod 0700 "$RESTORE_HELPER" "$STATE/rollback.sh"
}

schedule_rollback() {
  [ -f "$STATE/committed" ] || return 0
  touch "$STATE/rollback-pending"
  journal rollback scheduled
}
