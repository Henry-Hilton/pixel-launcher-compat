"""Public APKMirror adapter. No account/API key, CAPTCHA bypass or private endpoint."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import http.cookiejar
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
from bs4 import BeautifulSoup

ORIGIN = 'https://www.apkmirror.com'
UA = 'PixelLauncherCompat/0.5 (personal Android compatibility builder)'

class MirrorError(RuntimeError):
    pass

def safe_url(url: str) -> str:
    p = urllib.parse.urlparse(url)
    if p.scheme != 'https' or not (p.hostname == 'apkmirror.com' or
                                  (p.hostname or '').endswith('.apkmirror.com') or
                                  (p.hostname or '').endswith('.r2.cloudflarestorage.com')):
        raise MirrorError(f'Untrusted download destination: {p.hostname}')
    if p.username or p.password:
        raise MirrorError('Credentials in download URL are not supported')
    return url

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

@dataclass
class Variant:
    url: str
    title: str
    uploaded: str
    min_sdk: int
    architectures: list[str]
    package: str
    version: str
    version_code: int
    sha256: str
    signer_sha256: str
    format: str

    def compatible(self, sdk: int, abi: str) -> bool:
        return self.min_sdk <= sdk and (not self.architectures or
            'noarch' in self.architectures or abi in self.architectures)

def android_major(sdk: int) -> int:
    if sdk < 36:
        raise MirrorError('Android 16 / API 36 or later required')
    # Explicit mapping: never guess future Android/API relationships.
    try:
        return {36:16, 37:17}[sdk]
    except KeyError:
        raise MirrorError(f'No Android-major mapping for API {sdk}; update the catalog')

def parse_variant(url: str, raw: bytes) -> Variant:
    soup = BeautifulSoup(raw, 'html.parser')
    detail = soup.select_one('.apk-detail-table')
    safe = soup.select_one('#safeDownload')
    if detail is None or safe is None:
        raise MirrorError('APKMirror variant layout changed or access was blocked')
    text = detail.get_text(' ', strip=True)
    security = safe.get_text(' ', strip=True)
    def match(pattern, value=text):
        m = re.search(pattern, value, re.I)
        if not m:
            raise MirrorError(f'Missing variant metadata: {pattern}')
        return m.group(1).strip()
    version = match(r'Version:\s*(.*?)\s*\(\s*\d+\s*\)')
    version_code = int(match(r'Version:.*?\(\s*(\d+)\s*\)'))
    package = match(r'Package:\s*([a-zA-Z0-9_.]+)')
    min_sdk = int(match(r'Min:.*?API\s*(\d+)'))
    hashes = re.findall(r'SHA-256:\s*([a-f0-9]{64})', security, re.I)
    if len(hashes) != 2:
        raise MirrorError('Expected certificate fingerprint and file SHA-256')
    dt = detail.select_one('[data-utcdate]')
    if dt is None:
        raise MirrorError('Missing upload date')
    uploaded = datetime.strptime(dt['data-utcdate'], '%m/%d/%Y %H:%M UTC').replace(
        tzinfo=timezone.utc).isoformat()
    arch = sorted(set(re.findall(r'\b(?:arm64-v8a|armeabi-v7a|x86_64|x86|noarch)\b', text)))
    h1 = soup.select_one('h1')
    title = h1.get_text(' ', strip=True) if h1 else package
    download = soup.select_one('a.downloadButton[href]')
    kind = 'apkm' if download and 'bundle' in download.get_text(' ',strip=True).lower() else 'apk'
    return Variant(url, title, uploaded, min_sdk, arch, package, version,
                   version_code, hashes[1].lower(), hashes[0].lower(), kind)

def variant_links(raw: bytes, base: str, sdk=None, abi=None) -> list[str]:
    soup = BeautifulSoup(raw, 'html.parser')
    # Variant tables are a single release; exclude unrelated older-release recommendations.
    links = []
    for row in soup.select('.table-row'):
        a = row.select_one('a[href*="android-apk-download/"]')
        if a:
            text = row.get_text(' ',strip=True)
            if abi and any(x in text for x in ['arm64-v8a','armeabi-v7a','x86_64','x86']):
                if abi not in text:
                    continue
            minimum = re.search(r'Android (\d+)(?:\.\d+)?\+',text)
            if sdk and minimum and int(minimum.group(1)) > android_major(sdk):
                continue
            url = urllib.parse.urljoin(base, a['href']).split('#')[0]
            dt = row.select_one('[data-utcdate]')
            stamp = datetime.strptime(dt['data-utcdate'],'%m/%d/%Y %H:%M UTC') if dt else datetime.min
            if url not in [x[1] for x in links]:
                links.append((stamp,safe_url(url)))
    return [url for _,url in sorted(links,reverse=True)]

class Mirror:
    def __init__(self, cache: Path):
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.opener = urllib.request.build_opener(SafeRedirect(),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.last_request = 0.0

    def open(self, url):
        safe_url(url)
        time.sleep(max(0,5-(time.monotonic()-self.last_request)))
        self.last_request = time.monotonic()
        try:
            return self.opener.open(urllib.request.Request(url, headers={'User-Agent':UA}), timeout=60)
        except urllib.error.HTTPError as exc:
            raise MirrorError(f'APKMirror returned HTTP {exc.code} for {urllib.parse.urlsplit(url).path}; no device changes made') from exc

    def page(self, url):
        saved = self.cache / ('page-' + hashlib.sha256(url.encode()).hexdigest() + '.html')
        ttl=86400 if '-android-apk-download/' in url and '/download/' not in url else 300
        if saved.exists() and time.time()-saved.stat().st_mtime < ttl:
            return saved.read_bytes()
        with self.open(url) as response:
            data = response.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise MirrorError('HTML response exceeds size limit')
        if b'cf-chl-' in data or b'Just a moment...' in data:
            raise MirrorError('APKMirror requires interactive access; use a downloaded verified APK')
        saved.write_bytes(data)
        return data

    def launcher(self, sdk: int, abi: str) -> Variant:
        major = android_major(sdk)
        url = f'{ORIGIN}/apk/google-inc/pixel-launcher/pixel-launcher-{major}-release/'
        candidates = self.release(url, sdk, abi, 'com.google.android.apps.nexuslauncher')
        # SDK minimum must match this Android release; no cross-major substitutions.
        candidates = [v for v in candidates if v.min_sdk == sdk and v.version == str(major)]
        if not candidates:
            raise MirrorError(f'No compatible stable Pixel Launcher {major} APK found')
        return max(candidates, key=lambda v:(v.uploaded, v.version_code, v.url))

    def release(self, url, sdk, abi, package):
        links = variant_links(self.page(url), url, sdk, abi)
        found = []
        for link in links:
            variant = parse_variant(link, self.page(link))
            if variant.package == package and variant.compatible(sdk,abi):
                found.append(variant)
                # Ordered by upload date, not by the often-reused versionCode.
                # One compatible variant is enough; don't fetch all older uploads.
                break
        return found

    def latest(self, slug, package, sdk, abi, pages=3, flavor=None):
        base = f'{ORIGIN}/apk/google-inc/{slug}/'
        visited = set()
        # Root variant summaries expose newest uploads per SDK/ABI. Prefer these
        # over walking many historical release pages (which also wastes bandwidth).
        root = BeautifulSoup(self.page(base),'html.parser')
        if flavor:
            filters=[]
            for row in root.select('.table-row'):
                text=row.get_text(' ',strip=True)
                minimum=re.search(r'Android (\d+)(?:\.\d+)?\+',text)
                if not minimum or int(minimum.group(1))>android_major(sdk) or abi not in text:
                    continue
                first=row.select_one('a[href*="variant-"]')
                if first:
                    filters.append((int(minimum.group(1)),urllib.parse.urljoin(base,first['href'])))
            for _,filtered in sorted(set(filters),reverse=True):
                for n in range(1,pages+1):
                    listing=filtered if n==1 else filtered+f'page/{n}/'
                    page=BeautifulSoup(self.page(listing),'html.parser')
                    seen=set()
                    for a in page.select('.appRow a[href*="android-apk-download/"]'):
                        title=a.get_text(' ',strip=True)
                        if flavor.lower() not in title.lower() or re.search(r'\b(beta|alpha|canary|preview)\b',title,re.I):
                            continue
                        url=urllib.parse.urljoin(listing,a['href']).split('#')[0]
                        if url in seen: continue
                        seen.add(url)
                        variant=parse_variant(url,self.page(url))
                        if variant.package==package and variant.compatible(sdk,abi) and flavor.lower() in variant.version.lower():
                            return variant
                    if not page.select_one('a.next, a.nextpostslink'):
                        break
            raise MirrorError(f'No compatible {flavor} variant of {package} found')
        summaries=[]
        for row in root.select('.table-row'):
            text=row.get_text(' ',strip=True)
            if 'Latest:' not in text or re.search(r'\b(beta|alpha|canary|preview)\b',text,re.I):
                continue
            if flavor and flavor.lower() not in text.lower():
                continue
            minimum=re.search(r'Android (\d+)(?:\.\d+)?\+',text)
            if minimum and int(minimum.group(1))>android_major(sdk):
                continue
            if any(x in text for x in ['arm64-v8a','arm-v7a','x86_64','x86']) and abi not in text:
                continue
            links=[urllib.parse.urljoin(base,a['href']).split('#')[0] for a in row.select('a[href]')]
            link=next((x for x in links if x.startswith(base) and re.search(r'-release/?$',x)),None)
            if link:
                date=re.search(r'on ([A-Za-z]+ \d+, \d{4})',text)
                stamp=datetime.strptime(date.group(1),'%B %d, %Y') if date else datetime.min
                # Pixel system components should prefer the device's Android
                # generation over a later re-upload of an older-generation build.
                generation=int(minimum.group(1)) if minimum else 0
                summaries.append((generation,stamp,link))
        for _,_,release in sorted(set(summaries),reverse=True):
            visited.add(release)
            candidates=self.release(release,sdk,abi,package)
            candidates=[v for v in candidates if not flavor or flavor.lower() in v.version.lower()]
            if candidates:
                return max(candidates,key=lambda v:(v.uploaded,v.version_code,v.url))
        for page_num in range(1, pages+1):
            url = base if page_num == 1 else base + f'page/{page_num}/'
            soup = BeautifulSoup(self.page(url), 'html.parser')
            releases = []
            for a in soup.select('.appRow a[href], h5 a[href]'):
                link = urllib.parse.urljoin(url,a['href']).split('#')[0]
                if link.startswith(base) and re.search(r'-release/?$',link) and link not in visited:
                    title = a.get_text(' ',strip=True)
                    if re.search(r'\b(beta|alpha|canary|preview)\b',title,re.I):
                        continue
                    releases.append(link)
                    visited.add(link)
            for release in releases:
                candidates = self.release(release,sdk,abi,package)
                candidates=[v for v in candidates if not flavor or flavor.lower() in v.version.lower()]
                if candidates:
                    return max(candidates,key=lambda v:(v.version_code,v.uploaded,v.url))
        raise MirrorError(f'No compatible stable {package} found in {pages} release pages')

    def download(self, variant: Variant) -> Path:
        dest = self.cache / (variant.sha256 + '.' + variant.format)
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == variant.sha256:
            return dest
        soup = BeautifulSoup(self.page(variant.url),'html.parser')
        button = soup.select_one('a.downloadButton[href]')
        if not button:
            raise MirrorError('No public APKMirror download button')
        landing = urllib.parse.urljoin(variant.url,button['href'])
        soup = BeautifulSoup(self.page(landing),'html.parser')
        link = soup.select_one('a#download-link[href]') or soup.select_one('a[href*="/wp-content/themes/APKMirror/download.php"]')
        if not link:
            # The public landing page may use a normal "click here" link.
            link = next((a for a in soup.select('a[href]') if 'here' in a.get_text(' ',strip=True).lower()
                         and ('download' in a['href'] or 'dl.php' in a['href'])),None)
        if not link:
            raise MirrorError('Download link unavailable; no CAPTCHA or access-control bypass attempted')
        download_url = urllib.parse.urljoin(landing,link['href'])
        partial = dest.with_suffix(dest.suffix+'.part')
        digest = hashlib.sha256()
        total = 0
        try:
            with self.open(download_url) as response, partial.open('wb') as output:
                while block := response.read(1024*1024):
                    total += len(block)
                    if total > 1024*1024*1024:
                        raise MirrorError('APK exceeds 1 GiB limit')
                    digest.update(block)
                    output.write(block)
            if digest.hexdigest() != variant.sha256:
                raise MirrorError('Downloaded bytes do not match APKMirror file SHA-256')
            partial.replace(dest)
        finally:
            partial.unlink(missing_ok=True)
        return dest

if __name__ == '__main__':
    import argparse, json
    cli = argparse.ArgumentParser()
    cli.add_argument('--sdk',required=True,type=int)
    cli.add_argument('--abi',default='arm64-v8a')
    cli.add_argument('--download',action='store_true')
    cli.add_argument('--cache',type=Path,default=Path(__file__).parent/'downloads')
    args = cli.parse_args()
    mirror = Mirror(args.cache)
    variant = mirror.launcher(args.sdk,args.abi)
    print(json.dumps(asdict(variant),indent=2))
    if args.download:
        print(mirror.download(variant))
