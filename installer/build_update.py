"""Build an APK-free metadata update from the exact tested full bundle."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile
from release import VERSION, VERSION_CODE, REPOSITORY, module_prop

HERE = Path(__file__).resolve().parent

def build(source: Path, output: Path):
    with zipfile.ZipFile(source) as archive:
        manifest=archive.read('SHA256SUMS')
        lock=archive.read('release-lock.json')
        profile=json.loads(lock)
        if not profile.get('profile_supported') or profile['android_sdk']!=36 or profile['abi']!='arm64-v8a':
            raise ValueError('Expected the supported Android 16 arm64 full bundle')
        if set(profile['components'])!={'launcher','google','intelligence','private-compute','wallpapers'}:
            raise ValueError('Updater requires the tested full component bundle')
        # The updater must not accept a corrupted local source ZIP.
        for line in manifest.decode().splitlines():
            digest,name=line.split('  ',1)
            if hashlib.sha256(archive.read(name)).hexdigest()!=digest:
                raise ValueError(f'Source payload hash mismatch: {name}')
    script=(HERE/'update_only.sh').read_text().replace('@MANIFEST_SHA@',hashlib.sha256(manifest).hexdigest()).replace('@LOCK_SHA@',hashlib.sha256(lock).hexdigest())
    output.mkdir(parents=True,exist_ok=True)
    target=output/f'PixelLauncher-Compat-v{VERSION}-update.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in {'module.prop':module_prop(),'customize.sh':script.encode()}.items():
            info=zipfile.ZipInfo(name); info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o100755 if name.endswith('.sh') else 0o100644)<<16
            archive.writestr(info,data)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    (output/'SHA256SUMS').write_text(f'{digest}  {target.name}\n',encoding='utf-8')
    update=json.loads((HERE.parent/'update.json').read_text())
    assert update['version']==VERSION and update['versionCode']==VERSION_CODE
    assert update['zipUrl']==f'{REPOSITORY}/releases/download/v{VERSION}/{target.name}'
    print(target)
    return target

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,default=HERE/'release-out')
    args=parser.parse_args()
    build(args.source,args.output)
