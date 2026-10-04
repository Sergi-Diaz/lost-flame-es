"""Prueba PowerShell 5.1 en Windows; admite pwsh para validar el motor en Linux."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from test_instalacion import builder

ROOT = Path(__file__).resolve().parents[1]


def main(powershell):
    with tempfile.TemporaryDirectory(prefix='lostflame-windows-') as td:
        root = Path(td)
        package = root / 'Paquete español'
        game = root / 'Juego con espacios y ñ'
        backup = root / 'Respaldos fuera de Steam'
        game.mkdir(); (package / 'parche').mkdir(parents=True)
        shutil.copy2(ROOT / 'Instalar.ps1', package / 'Instalar.ps1')
        jar = game / 'LostFlame.jar'
        with zipfile.ZipFile(jar, 'w') as z:
            z.writestr('texts/test.json', b'{"text":"English"}')
            z.writestr('native/windows.dll', b'native platform file')
        original = jar.read_bytes()
        target = root / 'target.jar'
        with zipfile.ZipFile(target, 'w') as z:
            z.writestr('texts/test.json', b'{"text":"Espa\\u00f1ol"}')
            z.writestr('native/windows.dll', b'native platform file')
            z.writestr('translation/new.class', b'new code')
        patch = package / 'parche/parche.json'
        builder.build(jar, target, patch)

        def run(restore=False, success=True):
            command = [powershell, '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                       '-File', str(package / 'Instalar.ps1'), '-SinVentana',
                       '-Carpeta', str(game), '-RaizRespaldos', str(backup)]
            if restore:
                command.append('-Restaurar')
            result = subprocess.run(command, capture_output=True, text=True)
            if (result.returncode == 0) != success:
                raise AssertionError(result.stdout + result.stderr)

        run()
        installed = jar.read_bytes()
        with zipfile.ZipFile(jar) as z:
            assert z.read('texts/test.json') == b'{"text":"Espa\\u00f1ol"}'
            assert z.read('native/windows.dll') == b'native platform file'
            assert z.read('translation/new.class') == b'new code'
        run()
        assert installed == jar.read_bytes(), 'Reinstalar no debe cambiar el juego.'
        run(restore=True)
        assert original == jar.read_bytes(), 'La restauracion debe ser exacta.'
        run()
        jar.write_bytes(b'Steam update')
        run(restore=True, success=False)
        assert jar.read_bytes() == b'Steam update', 'No debe sobrescribir una actualizacion.'
        jar.write_bytes(original)
        import json
        payload = json.loads(patch.read_text())
        payload['entradas'][0]['operaciones'] = ['AA==']
        patch.write_text(json.dumps(payload))
        run(success=False)
        assert jar.read_bytes() == original, 'Un parche danado no debe cambiar el juego.'
        with zipfile.ZipFile(jar, 'w') as z:
            z.writestr('texts/test.json', b'new upstream version')
        updated = jar.read_bytes()
        run(success=False)
        assert jar.read_bytes() == updated, 'Una version incompatible debe conservarse.'
        print('PowerShell: instalacion, reinstalacion, restauracion, cambios de Steam, '
              'parche danado, nombres con espacios y caracteres no ASCII: OK')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--powershell', default='powershell.exe')
    main(p.parse_args().powershell)
