# Pixel Launcher Compatibility 0.5 device verification

Test date: 23 October 2026. Device: onyx / 25053PC47G, Android 16 API 36,
build BP4A.251205.006, KernelSU + NoMount + Vector.

Tested full ZIP SHA-256:
`8ba65f9340e2dc51ac4f57c28e42221bc261dcd1045fc6dd8e1107cdf2c9210a`

## Passed

- Host resolver/signature/rollback/startup regression suite: 17 tests.
- Real Android 16 and Android 17 launcher downloads and APK signature checks.
  Android 17 was verified for API 37, not installed on this Android 16 phone.
- Full ZIP hash verification and installation through KernelSU.
- Reboot: Pixel automatically selected as HOME, with privileged/updated-system-app
  status and package-scoped hidden-API exemption.
- HOME, app drawer, Calculator local-search result, and Recents cards.
- Google SearchActivity and its native-library-dependent search process started.
- Google wallpaper customization picker opened and displayed previews.
- System Intelligence prediction, Search UI and Smartspace providers bound by Android.
- Clean crash buffer during the corrected bundle's basic interactive tests.
- Full automatic uninstall + reboot: original Launcher3 HOME and Recents restored;
  Google app, System Intelligence, Private Compute Services, wallpaper picker and
  module-owned hook absent. Their `/data/user/0` and `/data/user_de/0` directories
  were absent. Module, rollback state and service.d helper were removed.
- Original user-installed Pixel Launcher APK was retained throughout cleanup.

## Fixes found during device testing

The first full build changed the launcher's system APK filename and reused a stale
parsed-package cache. Preserve `PixelLauncher.apk` and invalidate only its parser
cache on installation. Select Pixel HOME before waiting for boot completion.

System partition apps need their APK-provided native libraries staged separately;
otherwise the Google search process fails to load `libmappedcountercacheversionjni.so`.
The final bundle includes the matching ABI libraries and their checksums.

Root-manager logging file descriptors caused Binder shell transactions to fail
during automatic rollback. Commands now capture both output streams through pipes
and preserve their exit status. The complete automatic uninstall cycle was repeated
successfully after this fix, without manually running the cleanup helper.

## Limits

This is a tested Android 16 / onyx profile, not a universal non-Pixel port. The
preparer selects Android 17 correctly but refuses unported launcher/SystemUI
digests. Provider binding and app startup do not prove every optional feature:
Discover, account/server-dependent suggestions, voice models, overview OCR/Select,
and Pixel-specific hardware features have not received end-to-end verification.
No account sign-in, permission-consent acceptance, or wallpaper change was performed.

The verified bundle is reinstalled after the uninstall test so the phone can
continue using Pixel Launcher. Its new uninstall baseline is the original Launcher3.

Final reboot finding: SystemUI restarted once while reinflating its notification
section header during a theme/configuration change. The cause was
`IndexOutOfBoundsException` in `StringBlock.nativeGetString` while `TextView` loaded
a font. SystemUI recovered (PID 6460); Pixel remained PID 4917. Repeated HOME,
drawer, Recents and notification-shade checks did not reproduce it. Its relationship
to the module is unproven; this prevents claiming a completely clean final boot.
The trace is saved as `out-full/final-boot-crash.txt`.
