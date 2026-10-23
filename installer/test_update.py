from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import unittest
from release import VERSION, VERSION_CODE, UPDATE_URL, module_prop

HERE=Path(__file__).resolve().parent

class UpdateTests(unittest.TestCase):
    def simulate(self, *, installed=True, corrupt=False, pending=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); active=root/'active'; stage=root/'stage'; state=root/'state'
            active.mkdir(); stage.mkdir(); state.mkdir()
            (state/'committed').write_text('1')
            (state/'home-role-before').write_text('com.original.launcher')
            if pending: (state/'rollback-pending').touch()
            for name in ['system','hook','permissions']:
                (active/name).mkdir()
            (active/'system/test.apk').write_bytes(b'verified installed APK')
            for name in ['components.tsv','requested-permissions.txt','rom-privileged.txt','service.sh',
                         'action.sh','android_state.sh','rollback.sh','uninstall.sh','customize.sh','README.md']:
                (active/name).write_text('original '+name)
            lock=b'{"profile_supported":true}'
            (active/'release-lock.json').write_bytes(lock)
            manifest=f'{hashlib.sha256((active/"system/test.apk").read_bytes()).hexdigest()}  system/test.apk\n'.encode()
            (active/'SHA256SUMS').write_bytes(manifest)
            if installed: (active/'module.prop').write_text('id=pixel_launcher_compat\nversionCode=5\n')
            if corrupt: (active/'system/test.apk').write_bytes(b'corrupt')
            script=(HERE/'update_only.sh').read_text().replace('/data/adb/modules/pixel_launcher_compat',active.as_posix()).replace('/data/adb/pixel_launcher_compat_state',state.as_posix())
            script=script.replace('@MANIFEST_SHA@',hashlib.sha256(manifest).hexdigest()).replace('@LOCK_SHA@',hashlib.sha256(lock).hexdigest())
            metadata=root/'metadata'; metadata.write_bytes(module_prop())
            harness=root/'test.sh'
            harness.write_text(f'''
BOOTMODE=true
MODPATH='{stage.as_posix()}'
ZIPFILE=unused
abort() {{ echo "$*" >&2; exit 1; }}
ui_print() {{ :; }}
set_perm_recursive() {{ :; }}
set_perm() {{ :; }}
getprop() {{ case "$1" in ro.build.version.sdk) echo 36;; *) echo arm64-v8a;; esac; }}
unzip() {{ cat '{metadata.as_posix()}'; }}
'''+script)
            result=subprocess.run(['C:/Program Files/Git/bin/bash.exe','--noprofile','--norc',str(harness)],capture_output=True,text=True)
            return result, {p.relative_to(stage).as_posix():p.read_bytes() for p in stage.rglob('*') if p.is_file()}, (state/'home-role-before').read_text()

    def test_metadata_and_update_json_match(self):
        update=json.loads((HERE.parent/'update.json').read_text())
        self.assertEqual((update['version'],update['versionCode']),(VERSION,VERSION_CODE))
        self.assertIn(f'updateJson={UPDATE_URL}\n',module_prop().decode())

    def test_update_retains_payload_and_original_baseline(self):
        result,files,baseline=self.simulate()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(files['module.prop'],module_prop())
        self.assertEqual(files['system/test.apk'],b'verified installed APK')
        self.assertEqual(files['rollback.sh'],b'original rollback.sh')
        self.assertEqual(baseline,'com.original.launcher')

    def test_fresh_install_rejected_before_copy(self):
        result,files,_=self.simulate(installed=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(files,{})

    def test_corruption_rejected_before_copy(self):
        result,files,_=self.simulate(corrupt=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(files,{})

    def test_pending_rollback_rejected_before_copy(self):
        result,files,_=self.simulate(pending=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(files,{})

if __name__=='__main__': unittest.main()
