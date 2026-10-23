# 0.5.1

- Add the public root-manager update manifest and `updateJson` metadata.
- This small update ZIP upgrades the verified 0.5.0 full bundle in place. It
  contains no Google APKs; it verifies and retains the installed payload.
- Original uninstall ownership and HOME baseline are preserved. No app or app
  data changes are made by this metadata update. Reboot after installing.
- Requires the tested onyx Android 16 full-bundle profile. Fresh installations,
  modified payloads, and other profiles must use the host preparation tool.
- Compatibility remains experimental. The recovered SystemUI font-resource
  crash and unverified optional features documented in the test report remain.
