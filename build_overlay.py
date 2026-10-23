from pathlib import Path
import zipfile
import subprocess

p = Path(__file__).resolve().parent
with zipfile.ZipFile(p / 'tools/apktool.jar') as z:
    (p / 'tools/aapt2.exe').write_bytes(z.read('prebuilt/windows/aapt2.exe'))
o = p / 'recents-overlay'
(o / 'res/values').mkdir(parents=True, exist_ok=True)
(o / 'AndroidManifest.xml').write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="dev.henry.pixellauncher.recents.overlay" android:versionCode="2" android:versionName="0.2.0"><uses-sdk android:minSdkVersion="36" android:targetSdkVersion="36"/><overlay android:targetPackage="android" android:isStatic="true" android:priority="999"/><application android:hasCode="false" android:label="Pixel Launcher Recents Compatibility"/></manifest>''', encoding='utf-8')
(o / 'res/values/config.xml').write_text('''<resources><string name="config_recentsComponentName" translatable="false">com.google.android.apps.nexuslauncher/com.android.quickstep.RecentsActivity</string></resources>''', encoding='utf-8')
subprocess.run([str(p / 'tools/aapt2.exe'), 'compile', '--dir', str(o / 'res'), '-o', str(o / 'compiled.zip')], check=True)
subprocess.run([str(p / 'tools/aapt2.exe'), 'link', '-I', str(p / 'framework-res.apk'), '--manifest', str(o / 'AndroidManifest.xml'), '-o', str(o / 'recents-unsigned.apk'), str(o / 'compiled.zip')], check=True)
subprocess.run(['java', '-jar', str(p / 'tools/uber-apk-signer.jar'), '--apks', str(o / 'recents-unsigned.apk'), '--out', str(o / 'signed')], check=True)
