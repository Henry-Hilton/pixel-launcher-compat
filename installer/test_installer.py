from dataclasses import replace
from pathlib import Path
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from mirror import Mirror, MirrorError, Variant, android_major, parse_variant, safe_url, variant_links
from prepare import artifact_files, provider_components, inspect_apk, run, ROOT

HERE=Path(__file__).resolve().parent
VARIANT_URL='https://www.apkmirror.com/apk/google-inc/pixel-launcher/pixel-launcher-16-release/pixel-launcher-16-33-android-apk-download/'

def fixture(sdk=36,version='16',arch='noarch',date='06/22/2026 21:30 UTC'):
    return f'''<h1>Pixel Launcher {version}</h1><div class="apk-detail-table">
      Version: {version} (907) Package: com.google.android.apps.nexuslauncher
      Min: Android {version} (API {sdk}) {arch}
      <span data-utcdate="{date}"></span></div><div id="safeDownload">
      SHA-256: {'a'*64} APK file hashes SHA-256: {'b'*64}</div>'''.encode()

class ResolverTests(unittest.TestCase):
    def test_pixel_flavor_uses_exact_android_variant_not_generic_oem(self):
        base='https://www.apkmirror.com/apk/google-inc/device-personalization-services/'
        rows=b'''<div class="table-row">(arm64-v8a) (Android 16+) Latest: B.30.playstore.oemfull on October 20, 2026
          <a href="variant-sdk36/">variants</a></div>'''.replace(b'variant-sdk36',b'variant-%7B36%7D')
        listing=b'''<div class="appRow"><a href="/apk/google-inc/device-personalization-services/release/pixel16-android-apk-download/">Intelligence B.28.pixel10 Android 16+</a></div>'''
        class Fake(Mirror):
            def page(self,url):
                if url==base: return rows
                if 'variant-' in url: return listing
                return fixture().replace(b'16 (907)',b'B.28.pixel10 (907)').replace(b'com.google.android.apps.nexuslauncher',b'com.google.android.as')
        with tempfile.TemporaryDirectory() as tmp:
            result=Fake(Path(tmp)).latest('device-personalization-services','com.google.android.as',36,'arm64-v8a',flavor='pixel')
            self.assertEqual(result.version,'B.28.pixel10')
            self.assertEqual(result.min_sdk,36)
    def test_android16_never_selects17(self):
        class Fake(Mirror):
            def release(self,url,sdk,abi,package):
                self.selected_url=url
                return [parse_variant(VARIANT_URL,fixture()),
                        parse_variant(VARIANT_URL+'17',fixture(37,'17',date='09/11/2026 05:05 UTC'))]
        with tempfile.TemporaryDirectory() as tmp:
            mirror=Fake(Path(tmp))
            selected=mirror.launcher(36,'arm64-v8a')
            self.assertEqual(selected.version,'16')
            self.assertIn('pixel-launcher-16-release',mirror.selected_url)

    def test_android17_selects17(self):
        class Fake(Mirror):
            def release(self,*args):
                return [parse_variant(VARIANT_URL,fixture()),parse_variant(VARIANT_URL+'17',fixture(37,'17'))]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(Fake(Path(tmp)).launcher(37,'arm64-v8a').version,'17')

    def test_future_sdk_requires_explicit_mapping(self):
        with self.assertRaises(MirrorError): android_major(38)

    def test_reused_versioncode_sorted_by_upload(self):
        raw=b'''<div class="table-row">16 noarch Android 16+<a href="/old-android-apk-download/">16</a><span data-utcdate="01/01/2026 00:00 UTC"></span></div>
          <div class="table-row">16 noarch Android 16+<a href="/new-android-apk-download/">16</a><span data-utcdate="06/22/2026 21:30 UTC"></span></div>'''
        self.assertIn('new-',variant_links(raw,'https://www.apkmirror.com/',36,'arm64-v8a')[0])

    def test_wrong_architecture_filtered(self):
        raw=b'<div class="table-row">x86_64 Android 16+<a href="/x-android-apk-download/">16</a></div>'
        self.assertEqual(variant_links(raw,'https://www.apkmirror.com/',36,'arm64-v8a'),[])

    def test_unknown_host_and_plain_http_rejected(self):
        for url in ['http://www.apkmirror.com/a','https://apkmirror.com.attacker.invalid/a','https://attacker.invalid/file.apk']:
            with self.assertRaises(MirrorError): safe_url(url)

    def test_missing_security_metadata_rejected(self):
        with self.assertRaises(MirrorError): parse_variant(VARIANT_URL,b'<h1>Download APK</h1>')

    def test_corrupt_cache_never_treated_as_verified(self):
        v=parse_variant(VARIANT_URL,fixture())
        with tempfile.TemporaryDirectory() as tmp:
            apk=Path(tmp)/'broken.apk'; apk.write_bytes(b'not an apk')
            with patch('prepare.run') as command:
                with self.assertRaises(MirrorError): artifact_files(apk,v,36,'arm64-v8a',Path(tmp))
                command.assert_not_called()

    def test_http_failure_does_not_invoke_android(self):
        with tempfile.TemporaryDirectory() as tmp,patch('prepare.adb') as adb:
            m=Mirror(Path(tmp))
            with patch.object(m,'open',side_effect=MirrorError('HTTP 429')):
                with self.assertRaises(MirrorError): m.launcher(36,'arm64-v8a')
            adb.assert_not_called()

    def test_provider_names_come_from_declared_service_actions(self):
        dump='''E: manifest
  E: application
    E: service
      A: http://schemas.android.com/apk/res/android:name(0x01010003)="com.vendor.RealSearchService"
      E: intent-filter
        E: action
          A: http://schemas.android.com/apk/res/android:name(0x01010003)="android.service.search.SearchUiService"
    E: receiver
      A: http://schemas.android.com/apk/res/android:name(0x01010003)="com.vendor.NotAService"
'''
        with patch('prepare.run',return_value=dump):
            self.assertEqual(provider_components(Path('not-read.apk'),'com.google.android.as'),
                {'config_defaultSearchUiService':'com.google.android.as/com.vendor.RealSearchService'})

    def test_real_signer_mismatch_is_rejected(self):
        apk=ROOT/'pixel-launcher-original.apk'
        result=subprocess.run(['java','-cp',str(HERE)+';'+str(ROOT/'tools/uber-apk-signer.jar'),
             'VerifyApk',str(apk),'0'*64,'36'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Published signer absent',result.stderr)

class StartupTests(unittest.TestCase):
    def test_pixel_home_selected_before_waiting_for_boot_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            state=root/'state'; state.mkdir()
            log=root/'calls.log'
            (state/'android_state.sh').write_text('journal() { :; }\n')
            (state/'committed').write_text('1')
            (root/'components.tsv').write_text('')
            script=(HERE/'service.sh').read_text().replace('/data/adb/pixel_launcher_compat_state',state.as_posix())
            prelude=f'''
pm() {{ echo package:/system/priv-app/Pixel/base.apk; }}
cmd() {{
  case "$*" in
    'package set-home-activity '*) echo selected > "{log.as_posix()}" ;;
    'role get-role-holders '*) echo com.google.android.apps.nexuslauncher ;;
  esac
}}
getprop() {{
  [ -f "{log.as_posix()}" ] || {{ echo 'boot queried before HOME' >&2; exit 9; }}
  echo 1
}}
service() {{ echo search_ui; }}
'''
            harness=root/'test.sh'; harness.write_text(prelude+script)
            result=subprocess.run(['C:/Program Files/Git/bin/bash.exe','--noprofile','--norc',str(harness)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(log.exists())
            self.assertNotIn('boot queried before HOME',result.stderr)

class RollbackTests(unittest.TestCase):
    def simulate(self,hook_before='absent',recents='com.stock.launcher/Recents',fail_uninstall=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            state=root/'state'; state.mkdir()
            log=root/'calls.log'
            cli=root/'vector-cli'
            cli.write_text(f'#!/bin/sh\necho "VECTOR $*" >> "{log.as_posix()}"\n')
            for name,value in {
                'committed':'1','hook-before':hook_before,'home-role-before':'com.stock.launcher',
                'home-component-before':'com.stock.launcher/.Home','owned-packages':'com.new.component\n',
                'preexisting-packages':'com.existing.google\n','hook-enabled-before':'disabled',
                'hook-scope-before':'com.original.target/0\n',
            }.items(): (state/name).write_text(value)
            common=(HERE/'android_state.sh').read_text().replace('/data/adb/pixel_launcher_compat_state',state.as_posix()).replace('/data/adb/lspd/cli',cli.as_posix()).replace('/data/adb/service.d/pixel_launcher_compat_restore.sh',(root/'helper.sh').as_posix())
            (state/'android_state.sh').write_text(common)
            script=(HERE/'rollback.sh').read_text().replace('/data/adb/pixel_launcher_compat_state',state.as_posix()).replace('/data/adb/service.d/pixel_launcher_compat_restore.sh',(root/'helper.sh').as_posix())
            # No filesystem deletion is performed by the shell in this harness.
            prelude=f'''
getprop() {{ echo 1; }}
cmd() {{
  echo "CMD $*" >> "{log.as_posix()}"
  case "$*" in
    'overlay lookup '*) echo '{recents}' ;;
    'role get-role-holders '*) echo com.stock.launcher ;;
  esac
}}
pm() {{
  case "$1" in
    path) echo "package:/data/app/$2/base.apk" ;;
    uninstall) echo "UNINSTALL $2" >> "{log.as_posix()}"; {'return 1' if fail_uninstall else ':'} ;;
  esac
}}
rm() {{ echo "REMOVE $*" >> "{log.as_posix()}"; }}
'''
            harness=root/'test.sh'; harness.write_text(prelude+script)
            result=subprocess.run(['C:/Program Files/Git/bin/bash.exe','--noprofile','--norc',str(harness)],capture_output=True,text=True)
            calls=log.read_text() if log.exists() else ''
            return result.returncode,calls,(state/'journal.tsv').read_text() if (state/'journal.tsv').exists() else ''

    def test_uninstall_removes_only_owned_packages(self):
        status,calls,_=self.simulate()
        self.assertEqual(status,0,calls)
        self.assertIn('UNINSTALL com.new.component',calls)
        self.assertIn('UNINSTALL dev.henry.pixellauncher.compat',calls)
        self.assertNotIn('UNINSTALL com.existing.google',calls)

    def test_preexisting_hook_scope_and_state_restored(self):
        status,calls,_=self.simulate('present')
        self.assertEqual(status,0,calls)
        self.assertNotIn('UNINSTALL dev.henry.pixellauncher.compat',calls)
        self.assertIn('scope set dev.henry.pixellauncher.compat com.original.target/0',calls)
        self.assertIn('modules disable dev.henry.pixellauncher.compat',calls)

    def test_no_early_home_restore_while_module_overlay_active(self):
        status,calls,_=self.simulate(recents='com.google.android.apps.nexuslauncher/Recents')
        self.assertNotEqual(status,0)
        self.assertNotIn('CMD role add-role-holder',calls)
        self.assertNotIn('UNINSTALL',calls)

    def test_failed_uninstall_preserves_state_for_retry(self):
        status,calls,journal=self.simulate(fail_uninstall=True)
        self.assertNotEqual(status,0)
        self.assertNotIn('REMOVE -rf',calls)
        self.assertIn('retry-required',journal)

if __name__=='__main__': unittest.main(verbosity=2)
