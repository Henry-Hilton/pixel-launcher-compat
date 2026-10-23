# Pixel Launcher module — installer and rollback requirements

Requested outcome: install a compatible Pixel Launcher and the components needed for
optional launcher features, with reversible local changes when the module is removed.

## Release and download policy

- Select the newest stable release supported by the device SDK, architecture and the
  module's tested compatibility profile. The absolute newest release may require Android 17.
- Do not use versionCode alone as an identity: multiple different Pixel Launcher 16 APKs
  use versionCode 907. Pin APK digest, certificate identity and dependency versions.
- Fetch required artifacts before applying device changes. Verify package, signature,
  digest, SDK, architecture, split completeness and required native libraries.
- Use explicit sources and record source URL, version, digest and signer in a release manifest.
- Resolve new upstream releases during preparation/testing. Publish validated manifests;
  do not silently replace the tested launcher with an untested APK at installation time.
- A failed download or verification must leave the working installation intact.

## Components and features

- Pixel Launcher: core HOME, app drawer, folders, local app search, widgets and Recents.
- Google app: Google search integration, voice/Lens entry points and Discover.
- Android System Intelligence: supported Smartspace, predictions and Recents selection.
- Private Compute Services: dependency for supported System Intelligence functionality.
- Pixel wallpaper picker and its actual dependencies: supported Wallpaper & style and
  recent-wallpaper features. Do not replace the ROM picker without a tested restore path.
- Existing Google Play services are a prerequisite to assess, not something to replace blindly.
- Vector remains a prerequisite for the current hook approach; a standalone implementation
  is a separate engineering change.
- APK presence is not feature support. Check service availability, permission grants,
  framework interfaces and actual UI behavior. Missing SearchUiManager requires service
  integration; installing System Intelligence alone has not been shown to supply it.
- A feature is supported only after it passes its acceptance test. Hardware-dependent,
  account/server-controlled or incompatible features must be reported as unavailable.

## Ownership and reversibility

- Store the initial baseline outside the module's replaceable version directory and
  preserve it on upgrades. Never recapture an already modified state as the first baseline.
- Record original HOME component/role, package presence and versions, relevant enabled
  states, only the settings/overlay selections this module will change, and companion-hook
  enabled state/scope if it already exists.
- Keep a durable transaction journal identifying every module-owned change.
- Prefer systemless app/config/overlay placement. Do not permanently edit system partitions,
  replace framework binaries, or disable signature verification.
- Reuse compatible pre-existing applications; never remove them during uninstall. Abort
  an incompatible pre-existing-app update until its APK/data rollback is implemented.
- Track newly introduced packages separately. Removal must uninstall only module-owned
  additions and remove their module-owned data, retaining pre-existing apps and data.
- Restore HOME, affected settings/overlays and hook scope/state. Retain the ROM launcher.
- Restore through root-manager uninstall and reboot, including removal while user storage
  is locked. If a step cannot run until unlock, retain a narrowly scoped one-shot rollback
  helper and remove it after verified success.
- Partial installation and failed upgrades must roll back completed steps in reverse order.
- Module removal is not the same as deleting its directory manually; document recovery
  behavior for disable/safe mode and abrupt directory deletion separately.

## Acceptance tests

1. Clean install on the test ROM, including automatic downloads and validation.
2. Upgrade without replacing the initial rollback baseline.
3. HOME, drawer, app launch, local search and Recents interaction tests.
4. Google search, voice/Lens entry points and Discover, where supported.
5. At a Glance, predictions, Recents selection and wallpapers, each tested separately.
6. Reboot persistence and crash-log checks.
7. Uninstall and reboot: compare the journaled state to the initial baseline; confirm
   stock HOME/Recents, pre-existing package preservation and removal of owned additions.
8. Download failure, incompatible APK and interrupted-install rollback checks.

## Current status

v0.4 is the tested core-launcher prototype. It bundles the APK extracted from the user's
phone, is pinned to the tested SystemUI, and does not implement automatic companion downloads,
all optional services, baseline ownership tracking or complete HOME/settings restoration.
It must not be presented as meeting these expanded installer/rollback requirements yet.

Sources checked:
- https://www.apkmirror.com/apk/google-inc/pixel-launcher/
- https://support.google.com/pixelphone/answer/12112173
- https://developers.google.com/android/binary_transparency/google1p/overview
- https://github.com/topjohnwu/Magisk/blob/master/docs/guides.md
