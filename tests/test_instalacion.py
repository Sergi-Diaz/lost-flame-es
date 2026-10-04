import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load('installer', ROOT / 'instalar.py')
builder = load('builder', ROOT / 'herramientas/generar_parche.py')


class Installation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lostflame-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'Juego con espacios y ñ'
        self.game.mkdir()
        self.backups = self.root / 'respaldos'
        self.package = self.root / 'paquete'
        (self.package / 'parche').mkdir(parents=True)
        self.jar = self.game / 'LostFlame.jar'
        self.launcher = self.game / 'LostFlame'
        self.launcher.write_bytes(b'#!/bin/sh\necho original\n')
        self.launcher.chmod(0o755)
        with zipfile.ZipFile(self.jar, 'w') as z:
            z.writestr('texts/test.json', b'{"text":"English"}')
            z.writestr('native/windows.dll', b'native platform file')
        self.original = self.jar.read_bytes()
        target = self.root / 'target.jar'
        with zipfile.ZipFile(target, 'w') as z:
            z.writestr('texts/test.json', b'{"text":"Espa\\u00f1ol"}')
            z.writestr('native/windows.dll', b'native platform file')
            z.writestr('translation/new.class', b'new code')
        builder.build(self.jar, target, self.package / 'parche/parche.json')
        self.old_root = installer.ROOT
        installer.ROOT = self.package
        self.addCleanup(setattr, installer, 'ROOT', self.old_root)

    def test_install_idempotent_restore_and_native_files(self):
        installer.install(self.game, self.backups)
        installed = self.jar.read_bytes()
        with zipfile.ZipFile(self.jar) as z:
            self.assertEqual(z.read('native/windows.dll'), b'native platform file')
            self.assertEqual(z.read('translation/new.class'), b'new code')
        installer.install(self.game, self.backups)
        self.assertEqual(installed, self.jar.read_bytes())
        installer.restore(self.game, self.backups)
        self.assertEqual(self.jar.read_bytes(), self.original)
        self.assertEqual(self.launcher.read_bytes(), b'#!/bin/sh\necho original\n')

    def test_unknown_version_untouched(self):
        with zipfile.ZipFile(self.jar, 'w') as z:
            z.writestr('texts/test.json', b'new upstream version')
        before = self.jar.read_bytes()
        with self.assertRaisesRegex(ValueError, 'incompatible'):
            installer.install(self.game, self.backups)
        self.assertEqual(before, self.jar.read_bytes())
        self.assertFalse(self.backups.exists())

    def test_restore_does_not_overwrite_steam_update(self):
        installer.install(self.game, self.backups)
        self.jar.write_bytes(b'Steam update')
        with self.assertRaisesRegex(ValueError, 'cambió'):
            installer.restore(self.game, self.backups)
        self.assertEqual(self.jar.read_bytes(), b'Steam update')

    def test_damaged_patch_untouched(self):
        p = self.package / 'parche/parche.json'
        payload = json.loads(p.read_text())
        payload['entradas'][0]['operaciones'] = ['AA==']
        p.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, 'dañado'):
            installer.install(self.game, self.backups)
        self.assertEqual(self.jar.read_bytes(), self.original)

    def test_partial_installation_untouched(self):
        with zipfile.ZipFile(self.jar, 'w') as z:
            z.writestr('texts/test.json', b'{"text":"Espa\\u00f1ol"}')
            z.writestr('native/windows.dll', b'native platform file')
        before = self.jar.read_bytes()
        with self.assertRaisesRegex(ValueError, 'parcialmente'):
            installer.install(self.game, self.backups)
        self.assertEqual(self.jar.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
