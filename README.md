# Pixel Launcher Compatibility

Systemless Pixel Launcher compatibility module and Windows preparation tools.
The preparer downloads Android-matched APKs, verifies signatures and hashes, and
builds an offline flashable ZIP with ownership-aware uninstall rollback.

**Experimental: validated on one onyx Android 16 ROM.** This is not a universal
Android 16+ port. Android 17 download selection is implemented; untested launcher
and SystemUI digests are rejected before a flashable profile is generated.

## Features

- SDK/ABI-aware Pixel Launcher selection, with explicit Android 16/17 mapping.
- Optional Google app, Android System Intelligence, Private Compute Services,
  and Android-matched wallpaper picker downloads.
- APK package/version/SDK/ABI checks, SHA-256 verification, and authenticated
  certificate-rotation checks through Android apksig.
- Systemless privileged apps, ABI-specific native libraries, permission allowlists,
  and manifest-discovered provider overlays.
- Pixel-only Vector hooks adapting the tested ROM's framework interfaces.
- Persistent ownership journal: uninstall and reboot restore the original HOME
  and Recents, remove module-owned additions, and retain pre-existing apps.

## Build prerequisites

Use Windows with Python 3.10+, a JDK, Git Bash, and Android platform-tools on PATH.
The device needs USB debugging, root, Vector, and working systemless mounting.
The tested setup uses KernelSU and NoMount; other root managers are unverified.

This source repository intentionally excludes Google/ROM APKs, downloaded tools,
generated ZIPs, device logs, and screenshots. A fresh clone needs these local inputs:

- `tools/apktool.jar` (3.0.3) from [Apktool](https://github.com/iBotPeaches/Apktool).
- `tools/uber-apk-signer.jar` (1.3.0) from
  [uber-apk-signer](https://github.com/patrickfav/uber-apk-signer).
- `tools/module_installer.sh`, the installer script from
  [Magisk](https://github.com/topjohnwu/Magisk/blob/master/scripts/module_installer.sh).
- `framework-res.apk`, `SystemUI.apk`, and `package-device.txt` (the launcher's
  `dumpsys package` output) captured from the supported device.
- `pixel-launcher-original.apk`, the unchanged tested launcher APK. The current
  profile expects SHA-256
  `ee2e087ceac455b6c9b56c52eff12fd583dac3cb61f2110652ae664b469a201c`.

Do not substitute another ROM's inputs and assume compatibility. The hooks contain
ROM-specific Binder adapters and obfuscated launcher class names.

```powershell
python -m pip install -r installer/requirements.txt
python build_overlay.py
python build_hook.py
python build_module.py
cd installer
python prepare.py
python -m unittest test_installer -v
```

`build_overlay.py` extracts the bundled Windows aapt2 from Apktool. The first three
build scripts generate the legacy 0.4 base consumed by the 0.5 preparer. Install
the final **0.5** ZIP from `installer/out/`, not the intermediate legacy ZIP.
The real-APK signature test requires the local APK and signing tool inputs above.

See [installer instructions](installer/README.md) for component selection,
resume/offline preparation, installation and uninstall behavior.

## Updates

The module's `updateJson` URL is
https://raw.githubusercontent.com/Henry-Hilton/pixel-launcher-compat/main/update.json.
See [releases](https://github.com/Henry-Hilton/pixel-launcher-compat/releases) and
the [changelog](CHANGELOG.md). The 0.5.1 release is a small metadata update for
the exact tested full bundle; it reuses verified installed apps. Fresh installs
still require the preparation tool. Install 0.5.1 once and reboot before expecting
the root manager to detect later updates.

## Verification and limits

[Device test report](installer/DEVICE-TEST-v0.5.md) records the tested launcher
flows and successful automatic full-bundle uninstall/reboot cleanup. The final
reboot also had one recovered SystemUI font-resource crash; its relationship to
the module is unresolved. Discover, voice models, overview OCR/Select and other
account/server/hardware-dependent features are not fully verified.

Google APKs and third-party tools are obtained separately and retain their
respective licenses. This repository does not redistribute those binaries.
