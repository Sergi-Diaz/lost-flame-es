"""Instalación Linux y verificación del mismo formato que Windows."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import uuid
import zipfile

ROOT = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def apply_delta(old, entry):
    result = bytearray()
    for op in entry['operaciones']:
        if isinstance(op, str):
            result.extend(base64.b64decode(op, validate=True))
        else:
            offset, length = op
            if offset < 0 or length < 0 or offset + length > len(old):
                raise ValueError('Diferencia fuera de los límites del original.')
            result.extend(old[offset:offset + length])
    if len(result) != entry['longitud'] or sha(result) != entry['traducido']:
        raise ValueError('Parche dañado: ' + entry['nombre'])
    return bytes(result)


def replacements(jar, patch):
    updates, translated = {}, 0
    names = jar.namelist()
    if len(names) != len(set(names)):
        raise ValueError('El archivo contiene entradas duplicadas.')
    for entry in patch['entradas']:
        name = entry['nombre']
        old = jar.read(name) if name in names else b''
        current = sha(old) if name in names else None
        if current == entry['traducido']:
            translated += 1
        elif current == entry['original']:
            updates[name] = apply_delta(old, entry)
        else:
            raise ValueError('Versión incompatible o modificada: ' + name +
                             '. No se ha cambiado el juego.')
    if translated and updates:
        raise ValueError('Instalación parcialmente modificada. Restaura o verifica con Steam.')
    return updates


def check_running(game):
    for process in Path('/proc').glob('[0-9]*'):
        try:
            command = (process / 'cmdline').read_bytes()
            if b'LostFlame.jar' in command and (process / 'cwd').resolve() == game:
                raise ValueError('Cierra Lost Flame antes de continuar.')
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            pass


def backup_dir(game, backup_root=None):
    root = Path(backup_root) if backup_root else Path.home() / '.local/share/lost-flame-es/respaldos'
    return root / sha(str(game).encode())[:24]


def install(game, backup_root=None):
    game = Path(game).resolve()
    jar_path = game / 'LostFlame.jar'
    check_running(game)
    patch = json.loads((ROOT / 'parche/parche.json').read_text())
    backup = backup_dir(game, backup_root)
    state_path = backup / 'estado.json'
    with zipfile.ZipFile(jar_path) as source:
        updates = replacements(source, patch)
        if not updates:
            print('Esta traducción ya está instalada.')
            return
        before = file_sha(jar_path)
        token = uuid.uuid4().hex
        backup.mkdir(parents=True, exist_ok=True)
        original = backup / (token + '.jar')
        shutil.copy2(jar_path, original)
        if file_sha(original) != before:
            raise ValueError('La copia de seguridad no coincide con el juego.')
        fd, temp = tempfile.mkstemp(prefix='.lost-flame-es-', suffix='.jar', dir=game)
        os.close(fd)
        launcher = game / 'LostFlame'
        old_launcher = launcher.read_bytes() if launcher.exists() else None
        new_launcher = (b'#!/bin/sh\ncd "$(dirname "$0")" || exit 1\n'
                        b'exec env -u WAYLAND_DISPLAY XDG_SESSION_TYPE=x11 jre/bin/java '
                        b'-Dfile.encoding=UTF-8 -jar LostFlame.jar\n')
        try:
            with zipfile.ZipFile(temp, 'w') as target:
                for info in source.infolist():
                    target.writestr(info, updates.get(info.filename, source.read(info.filename)))
                for name, data in updates.items():
                    if name not in source.namelist():
                        target.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
            with zipfile.ZipFile(temp) as candidate:
                if candidate.testzip() or replacements(candidate, patch):
                    raise ValueError('No se pudo validar el archivo traducido.')
            after = file_sha(temp)
            os.chmod(temp, stat.S_IMODE(jar_path.stat().st_mode))
            check_running(game)
            if file_sha(jar_path) != before:
                raise ValueError('El juego cambió durante la instalación.')
            state = dict(original=original.name, sha_original=before, sha_instalado=after,
                         lanzador_original=base64.b64encode(old_launcher).decode() if old_launcher else None,
                         lanzador_instalado=sha(new_launcher) if old_launcher else None)
            pending = backup / ('estado-' + token + '.json')
            pending.write_text(json.dumps(state), encoding='utf-8')
            committed = False
            try:
                os.replace(temp, jar_path)
                committed = True
                if old_launcher:
                    launcher.write_bytes(new_launcher)
                os.replace(pending, state_path)
            except Exception:
                if committed:
                    shutil.copy2(original, temp)
                    os.replace(temp, jar_path)
                    if old_launcher:
                        launcher.write_bytes(old_launcher)
                raise
        finally:
            Path(temp).unlink(missing_ok=True)
    print('Traducción instalada. Respaldo: ' + str(backup))


def restore(game, backup_root=None):
    game = Path(game).resolve()
    check_running(game)
    backup = backup_dir(game, backup_root)
    state_path = backup / 'estado.json'
    state = json.loads(state_path.read_text())
    jar = game / 'LostFlame.jar'
    original = backup / state['original']
    if file_sha(jar) != state['sha_instalado']:
        raise ValueError('Steam u otro programa cambió el juego. Se conserva el respaldo; '
                         'no se sobrescribe esta versión.')
    if file_sha(original) != state['sha_original']:
        raise ValueError('El respaldo está dañado.')
    launcher = game / 'LostFlame'
    if state['lanzador_instalado'] and (not launcher.exists() or
                                       file_sha(launcher) != state['lanzador_instalado']):
        raise ValueError('El lanzador cambió. No se sobrescribe.')
    fd, temp = tempfile.mkstemp(prefix='.lost-flame-es-', suffix='.jar', dir=game)
    os.close(fd)
    try:
        shutil.copy2(original, temp)
        check_running(game)
        if file_sha(jar) != state['sha_instalado']:
            raise ValueError('El juego cambió durante la restauración.')
        os.replace(temp, jar)
        if state['lanzador_original']:
            launcher.write_bytes(base64.b64decode(state['lanzador_original']))
        state_path.unlink()
    finally:
        Path(temp).unlink(missing_ok=True)
    print('Juego original restaurado. La copia de seguridad se conserva.')


def find_games():
    libraries = set()
    for root in [Path.home() / '.steam/steam', Path.home() / '.steam/debian-installation',
                 Path.home() / '.local/share/Steam',
                 Path.home() / '.var/app/com.valvesoftware.Steam/.local/share/Steam']:
        libraries.add(root)
        vdf = root / 'steamapps/libraryfolders.vdf'
        if vdf.exists():
            libraries.update(Path(x.replace('\\\\', '\\')) for x in
                             re.findall(r'"path"\s*"([^"]+)"', vdf.read_text()))
    return sorted({(x / 'steamapps/common/Lost Flame').resolve() for x in libraries
                   if (x / 'steamapps/common/Lost Flame/LostFlame.jar').exists()})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Traducción de Lost Flame al español')
    p.add_argument('accion', choices=['instalar', 'restaurar'], nargs='?', default='instalar')
    p.add_argument('--carpeta', type=Path)
    a = p.parse_args()
    try:
        games = [a.carpeta] if a.carpeta else find_games()
        if len(games) != 1:
            raise ValueError('Indica la carpeta del juego con --carpeta "ruta/Lost Flame".')
        (install if a.accion == 'instalar' else restore)(games[0])
    except Exception as e:
        p.exit(1, str(e) + '\n')
