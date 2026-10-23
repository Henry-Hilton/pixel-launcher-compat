# Pixel Launcher Compatibility Installer 0.5

This release has two parts: a Windows preparation tool that downloads and verifies
the right APKs, and a device-specific ZIP installed through KernelSU/Magisk.
Downloads happen before flashing, so a network failure cannot half-install apps.

## Prepare a ZIP

Requirements: Python 3.10+, a JDK (java/javac), adb, USB debugging, root, Vector,
and working system-file mounting (NoMount is used on the tested phone).
Run from this directory with the phone connected:

```powershell
python prepare.py
```

This selects the stable Pixel Launcher 16 for API 36 or Pixel Launcher 17 for API 37.
It selects arm64-compatible components, prefers a Pixel System Intelligence build for
the device's Android generation, and prepares Google app, Android System Intelligence,
Private Compute Services, and the Android-matched Google wallpaper picker.

```powershell
python prepare.py --resume
python prepare.py --components
```

The first resumes a pinned preparation after a network interruption. The second prepares
only the launcher. To choose a subset, use `--components google intelligence private-compute`.
`--sdk 36 --abi arm64-v8a` can select downloads explicitly; connected-device profile
verification is still required before generating a flashable ZIP.

Outputs: `out/PixelLauncher-Compat-v0.5.0.zip`, `out/release-lock.json`, and a source
selection file. The lock records source pages, SDK, architecture, upload time, package,
version, file hash, signer fingerprint and service components. Unverified downloads are
never installed. APK v3/v3.1 certificate rotation is checked using apksig's verified lineage.

APKMirror has no documented public download API used by this project. The adapter follows
public pages and download links, observes HTTP failures/rate limits, and caches metadata
and verified files. It does not bypass CAPTCHA. A blocked source stops preparation;
`--resume` reuses the pinned selection and already verified downloads.

## Compatibility boundary

Version selection supports Android 16 and 17. The current code hooks are validated only
for the original v907 Android 16 launcher and the tested onyx ROM's SystemUI. A different
launcher digest or SystemUI is downloaded/verified but rejected as a flashable profile
until its interfaces are ported and tested. Selecting the right Android version is not
enough to prove binary compatibility. Future API levels require an explicit mapping.

Smartspace, search UI, app prediction and content-suggestion providers are discovered
from the actual downloaded System Intelligence manifest. A systemless resource overlay
selects those providers, enabling corresponding ROM services where the ROM supports them.
No service class names are guessed and no framework binaries are replaced.
Native libraries are copied from the verified APKs into each systemless app's
architecture-specific library directory. Their hashes are included in the ZIP's
checksum manifest. The launcher keeps its original system APK filename, and its
parsed-package cache is invalidated at install to prevent stale registration.

The component-status report confirms packages/services, not successful feature tests.
Account/server/hardware-controlled features can still be unavailable; they must be
tested independently. Google Play services is reused, never replaced by this module.

## Install and remove

Install the prepared ZIP in the root manager and reboot. Pre-existing companion apps
are reused and are not updated or removed. A different pre-existing launcher APK is
rejected because upgrading its data would require a separate data-migration rollback.
On boot, Pixel is selected as HOME as soon as PackageManager is ready. This is needed
because the Recents overlay moves recents-only permissions away from the ROM's Quickstep
launcher. The saved original HOME is restored during uninstall.

The initial baseline is stored outside the replaceable module folder. Upgrades preserve
it. Root-manager uninstall schedules restoration after reboot, once the Pixel Recents
overlay is gone: restore the original HOME, restore a pre-existing hook's scope/enabled
state or remove a module-owned hook, and remove module-owned apps. Successful cleanup
removes the journal, baseline and one-shot helper. Failed cleanup retains state for retry.

Use root-manager **uninstall**, then reboot. Manually deleting a module folder bypasses
its uninstall callback. Disabling/safe mode unmounts system files but is a recovery action,
not a full uninstall; it does not run ownership cleanup. A reboot is required for rollback.

The known 0.1–0.4 prototype can be migrated on the tested phone. Its recorded original
HOME is the ROM Launcher3, its hook was introduced by the prototype, and the original
user-installed Pixel Launcher is preserved. This migration is specific to this project.

## Validation

```powershell
python test_installer.py
```

The tests cover Android 16/17 separation, architecture filtering, reused version codes,
Pixel/OEM flavor selection, rejected hashes/signers, provider discovery, ownership cleanup,
scope restoration, pending-overlay protection, and retry after failed cleanup.
The startup regression test verifies HOME selection before waiting for boot completion.
The core 0.5 install/uninstall/reboot path has also been exercised on the connected phone:
stock HOME/Recents returned, original APK remained, helper/hook/module/state were removed.
See the generated test reports for optional-component and feature status.

Source tools live alongside the existing project tools in `../tools/`; the existing
tested base module, framework resource APK and compatibility-profile source files are
used by the builder. This folder is not an independently bootstrapped Android SDK.
