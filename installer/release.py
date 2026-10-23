"""Shared module release metadata."""
VERSION = '0.5.1'
VERSION_CODE = 6
REPOSITORY = 'https://github.com/Henry-Hilton/pixel-launcher-compat'
UPDATE_URL = 'https://raw.githubusercontent.com/Henry-Hilton/pixel-launcher-compat/main/update.json'

def module_prop():
    return ('id=pixel_launcher_compat\nname=Pixel Launcher Compatibility Installer\n'
            f'version={VERSION}\nversionCode={VERSION_CODE}\nauthor=Henry / Codex\n'
            'description=Android-aware verified downloads, systemless components and journaled rollback. Requires Vector; tested profile only.\n'
            f'updateJson={UPDATE_URL}\n').encode()
