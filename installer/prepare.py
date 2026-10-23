"""Download/verify a device-specific systemless module before touching the device."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
import re
import os
import subprocess
import zipfile
import xml.etree.ElementTree as ET

from mirror import Mirror, MirrorError, Variant, ORIGIN, android_major

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ANDROID_NS = '{http://schemas.android.com/apk/res/android}'
COMPONENTS = {
    'google': ('google-search','com.google.android.googlequicksearchbox'),
    'intelligence': ('device-personalization-services','com.google.android.as'),
    'private-compute': ('private-compute-services','com.google.android.as.oss'),
    'wallpapers': ('google-wallpaper-picker','com.google.android.apps.wallpaper'),
}

def run(*args):
    result = subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout + result.stderr

def adb(*args):
    return run('adb',*args).strip()

def inspect_apk(apk: Path, expected: Variant, sdk: int, abi: str):
    source=HERE/'VerifyApk.java'; compiled=HERE/'VerifyApk.class'
    if not compiled.exists() or compiled.stat().st_mtime<source.stat().st_mtime:
        run('javac','--release','11','-cp',ROOT/'tools/uber-apk-signer.jar',source)
    verification=run('java','-cp',os.pathsep.join([str(HERE),str(ROOT/'tools/uber-apk-signer.jar')]),
                     'VerifyApk',apk,expected.signer_sha256,sdk)
    if not verification.startswith('VERIFIED '):
        raise MirrorError('APK signing lineage verification did not succeed')
    badging = run(ROOT/'tools/aapt2.exe','dump','badging',apk)
    pkg = re.search(r"^package: name='([^']+)' versionCode='(\d+)'",badging,re.M)
    minimum = re.search(r"^(?:minSdkVersion|sdkVersion):'(\d+)'",badging,re.M)
    if not pkg or not minimum or pkg.group(1) != expected.package or int(pkg.group(2)) != expected.version_code:
        raise MirrorError('APK package/version does not match selected release metadata')
    if int(minimum.group(1)) > sdk:
        raise MirrorError('APK requires a newer Android SDK')
    natives = re.search(r'^native-code:(.*)$',badging,re.M)
    if natives and abi not in re.findall(r"'([^']+)'",natives.group(1)):
        raise MirrorError(f'APK native libraries do not support {abi}')
    permissions = sorted(set(re.findall(r"^uses-permission(?:-sdk-\d+)?: name='([^']+)'",badging,re.M)))
    return {'package':pkg.group(1),'min_sdk':int(minimum.group(1)),
            'requested_permissions':permissions,'badging':badging,
            'required_libraries':re.findall(r"^uses-library:'([^']+)'",badging,re.M)}

def provider_components(apk: Path, package: str):
    tree=run(ROOT/'tools/aapt2.exe','dump','xmltree',apk,'--file','AndroidManifest.xml')
    result={}; current=None; depth=0; lines=[]
    wanted={
        'android.service.appprediction.AppPredictionService':'config_defaultAppPredictionService',
        'android.service.smartspace.SmartspaceService':'config_defaultSmartspaceService',
        'android.service.search.SearchUiService':'config_defaultSearchUiService',
        'android.service.contentsuggestions.ContentSuggestionsService':'config_defaultContentSuggestionsService',
    }
    def commit():
        if not current: return
        chunk='\n'.join(lines)
        for action,resource in wanted.items():
            if '"'+action+'"' in chunk:
                name=package+current if current.startswith('.') else current
                result[resource]=package+'/'+name
    for line in tree.splitlines():
        indent=len(line)-len(line.lstrip())
        if re.match(r'\s*E:',line) and current and indent<=depth:
            commit(); current=None; lines=[]
        if re.match(r'\s*E: service\b',line):
            current=''; depth=indent; lines=[]
        if current is not None:
            lines.append(line)
            if not current and indent==depth+2:
                name=re.search(r'android:name\([^)]*\)="([^"]+)"',line)
                if name: current=name.group(1)
    commit()
    return result

def compile_services_overlay(resources, output):
    work=output/'services-overlay'
    (work/'res/values').mkdir(parents=True,exist_ok=True)
    manifest='''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="dev.henry.pixellauncher.services.overlay" android:versionCode="5" android:versionName="0.5.0"><uses-sdk android:minSdkVersion="36"/><overlay android:targetPackage="android" android:isStatic="true" android:priority="998"/><application android:hasCode="false"/></manifest>'''
    (work/'AndroidManifest.xml').write_text(manifest,encoding='utf-8')
    root=ET.Element('resources')
    for name,value in resources.items():
        ET.SubElement(root,'string',name=name,translatable='false').text=value
    ET.ElementTree(root).write(work/'res/values/config.xml',encoding='utf-8',xml_declaration=True)
    run(ROOT/'tools/aapt2.exe','compile','--dir',work/'res','-o',work/'compiled.zip')
    run(ROOT/'tools/aapt2.exe','link','-I',ROOT/'framework-res.apk','--manifest',work/'AndroidManifest.xml',
        '-o',work/'services.apk',work/'compiled.zip')
    run('java','-jar',ROOT/'tools/uber-apk-signer.jar','--apks',work/'services.apk','--out',work/'signed')
    return (work/'signed/services-aligned-debugSigned.apk').read_bytes()

def artifact_files(path: Path, variant: Variant, sdk: int, abi: str, work: Path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != variant.sha256:
        raise MirrorError('Artifact SHA-256 does not match release manifest')
    if variant.format == 'apk':
        files = [path]
    else:
        files = []
        target = work / variant.sha256
        target.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(path) as bundle:
            for item in bundle.infolist():
                if not item.filename.endswith('.apk'):
                    continue
                name = Path(item.filename).name
                if name != item.filename or item.file_size > 1024**3:
                    raise MirrorError('Unexpected APKM entry layout/size')
                dest = target / name
                dest.write_bytes(bundle.read(item))
                files.append(dest)
        if not any(x.name == 'base.apk' for x in files):
            raise MirrorError('Split bundle has no base.apk')
    inspected = [inspect_apk(x,variant,sdk,abi) for x in files]
    # Required native ABI splits are all verified, but unrelated ABI configurations
    # must not be installed on arm64-only devices.
    return files, inspected

def build(args):
    sdk = args.sdk or int(adb('shell','getprop','ro.build.version.sdk'))
    abi = args.abi or adb('shell','getprop','ro.product.cpu.abi')
    android_major(sdk)
    mirror = Mirror(args.cache)
    args.output.mkdir(parents=True,exist_ok=True)
    progress=args.output/'selection-progress.json'
    selected={}
    if getattr(args,'resume',False) and progress.exists():
        previous=json.loads(progress.read_text())
        if previous['sdk']!=sdk or previous['abi']!=abi:
            raise MirrorError('Cannot resume a selection for a different device SDK/ABI')
        selected={name:Variant(**item) for name,item in previous['components'].items()}
        completed=args.output/'release-lock.json'
        if completed.exists():
            old=json.loads(completed.read_text())
            if old.get('android_sdk')==sdk and old.get('abi')==abi:
                for name,item in old.get('components',{}).items():
                    selected.setdefault(name,Variant(**item))
    def save_selection():
        progress.write_text(json.dumps({'sdk':sdk,'abi':abi,'components':{n:asdict(v) for n,v in selected.items()}},indent=2)+'\n',encoding='utf-8')
    if 'launcher' not in selected:
        selected['launcher']=mirror.launcher(sdk,abi)
        save_selection()
    for name in args.components:
        if name in selected:
            continue
        slug,package = COMPONENTS[name]
        if name == 'wallpapers':
            major = android_major(sdk)
            url=f'{ORIGIN}/apk/google-inc/{slug}/google-wallpapers-{major}-release/'
            found=mirror.release(url,sdk,abi,package)
            if not found:
                raise MirrorError(f'No Wallpapers release compatible with Android {major}')
            selected[name]=found[0]
        else:
            selected[name]=mirror.latest(slug,package,sdk,abi,flavor='pixel' if name=='intelligence' else None)
        save_selection()
    selected={name:item for name,item in selected.items() if name=='launcher' or name in args.components}
    lock={'schema':1,'android_sdk':sdk,'abi':abi,'components':{},'feature_tests':{}}
    verified={}
    for name,variant in selected.items():
        print(f'Downloading and verifying {name}: {variant.version}',flush=True)
        artifact=mirror.download(variant)
        files,metadata=artifact_files(artifact,variant,sdk,abi,args.output/'work')
        verified[name]=(files,metadata)
        lock['components'][name]=asdict(variant)
    if getattr(args,'offline_profile',False):
        cached_profile=HERE/'device-profile.json'
        if not cached_profile.exists():
            raise MirrorError('No captured device profile is available for offline preparation')
        device_profile=json.loads(cached_profile.read_text())
        if device_profile['sdk']!=sdk or device_profile['abi']!=abi:
            raise MirrorError('Offline profile does not match requested SDK/ABI')
    else:
        systemui=adb('shell','pm','path','com.android.systemui').split('package:',1)[1].splitlines()[0]
        device_profile={'sdk':sdk,'abi':abi,'systemui_sha256':adb('shell','sha256sum',systemui).split()[0],
            'libraries':[x.split(':',1)[1] for x in adb('shell','pm','list','libraries').splitlines() if x.startswith('library:')]}
        (HERE/'device-profile.json').write_text(json.dumps(device_profile,indent=2)+'\n',encoding='utf-8')
    available_libraries=set(device_profile['libraries'])
    for name,(_,metadata) in verified.items():
        missing={library for m in metadata for library in m['required_libraries']} - available_libraries
        if missing:
            raise MirrorError(f'{name} requires missing shared libraries: {sorted(missing)}; device unchanged')
    # Hooks use obfuscated implementation names; SDK compatibility alone cannot prove
    # a new launcher binary works. Download 17 correctly, but refuse a 16-only hook profile.
    known_launcher=hashlib.sha256((ROOT/'pixel-launcher-original.apk').read_bytes()).hexdigest()
    systemui_hash=device_profile['systemui_sha256']
    known_systemui=hashlib.sha256((ROOT/'SystemUI.apk').read_bytes()).hexdigest()
    lock['profile_supported']=sdk==36 and selected['launcher'].sha256==known_launcher and systemui_hash==known_systemui
    lock['systemui_sha256']=systemui_hash
    (args.output/'release-lock.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
    if not lock['profile_supported']:
        raise MirrorError('Correct Android APKs downloaded and verified, but no tested hook profile for this launcher/ROM. Device unchanged.')
    base=ROOT/'PixelLauncher-Compat-v0.4.0-experimental.zip'
    if not base.exists():
        raise MirrorError('Build the v0.4 base module first')
    with zipfile.ZipFile(base) as archive:
        payload={name:archive.read(name) for name in archive.namelist() if not name.endswith('/')}
    if 'intelligence' in verified:
        provider=next((p for p in verified['intelligence'][0] if p.name=='base.apk'),verified['intelligence'][0][0])
        services=provider_components(provider,selected['intelligence'].package)
        if services:
            payload['system/product/overlay/PixelLauncherServicesCompat/PixelLauncherServicesCompat.apk']=compile_services_overlay(services,args.output)
        lock['service_components']=services
    rows=[]
    for name,(files,metadata) in verified.items():
        variant=selected[name]
        location='PixelLauncherCompat' if name=='launcher' else 'PixelCompat_'+name.replace('-','_')
        prefix=f'system/priv-app/{location}/'
        for old in [x for x in payload if x.startswith(prefix)]:
            del payload[old]
        native_dir={'arm64-v8a':'arm64','armeabi-v7a':'arm','x86_64':'x86_64','x86':'x86'}[abi]
        for i,path in enumerate(files):
            filename=('PixelLauncher.apk' if name=='launcher' else 'base.apk') if len(files)==1 else path.name
            payload[prefix+filename]=path.read_bytes()
            # System partition packages do not receive PackageInstaller's native
            # library extraction. Supply the original signed APK's libraries at
            # the directory PackageManager assigns to this privileged package.
            with zipfile.ZipFile(path) as apk:
                for item in apk.infolist():
                    parts=item.filename.split('/')
                    if len(parts)==3 and parts[:2]==['lib',abi] and parts[2].endswith('.so'):
                        target=prefix+'lib/'+native_dir+'/'+parts[2]
                        data=apk.read(item)
                        if target in payload and payload[target]!=data:
                            raise MirrorError(f'Conflicting native library across splits: {item.filename}')
                        payload[target]=data
        permissions=sorted({p for m in metadata for p in m['requested_permissions']})
        payload[f'permissions/{variant.package}.txt']=('\n'.join(permissions)+'\n').encode()
        rows.append(f'{variant.package}\t{prefix}\t{variant.sha256}\t{name}')
    payload['components.tsv']=('\n'.join(rows)+'\n').encode()
    payload['release-lock.json']=(json.dumps(lock,indent=2)+'\n').encode()
    (args.output/'release-lock.json').write_bytes(payload['release-lock.json'])
    config=ET.Element('config')
    for variant in selected.values():
        ET.SubElement(config,'hidden-api-whitelisted-app',package=variant.package)
    payload['system/etc/sysconfig/pixel-launcher-compat.xml']=ET.tostring(config,encoding='utf-8',xml_declaration=True)
    for filename in ['android_state.sh','rollback.sh','customize.sh','uninstall.sh','service.sh','action.sh','README.md']:
        payload[filename]=(HERE/filename).read_bytes().replace(b'\r\n',b'\n')
    payload['module.prop']=('id=pixel_launcher_compat\nname=Pixel Launcher Compatibility Installer\n'
        'version=0.5.0\nversionCode=5\nauthor=Henry / Codex\n'
        'description=Android-aware verified downloads, systemless components and journaled rollback. Requires Vector; tested profile only.\n').encode()
    checksum_names=[n for n in payload if n.endswith(('.apk','.so')) or n.startswith('permissions/') or n in ['components.tsv','release-lock.json']]
    payload['SHA256SUMS']=(''.join(f'{hashlib.sha256(payload[n]).hexdigest()}  {n}\n' for n in sorted(checksum_names))).encode()
    out=args.output/'PixelLauncher-Compat-v0.5.0.zip'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(payload.items()):
            info=zipfile.ZipInfo(name)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o100755 if name.endswith('.sh') or name.endswith('update-binary') else 0o100644)<<16
            archive.writestr(info,data)
    print(f'Built {out}')
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk',type=int)
    parser.add_argument('--abi')
    parser.add_argument('--components',nargs='*',choices=COMPONENTS,default=list(COMPONENTS))
    parser.add_argument('--cache',type=Path,default=HERE/'downloads')
    parser.add_argument('--output',type=Path,default=HERE/'out')
    parser.add_argument('--resume',action='store_true',help='Resume the saved, pinned selection without refetching its metadata')
    parser.add_argument('--offline-profile',action='store_true',help='Use the previously captured device profile; flash-time checks still enforce it')
    args=parser.parse_args()
    try:
        build(args)
    except (MirrorError,RuntimeError) as exc:
        parser.exit(1,f'ERROR: {exc}\n')
