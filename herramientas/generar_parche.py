"""Genera diferencias; las rutas del juego nunca se incorporan al paquete."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def delta(old, new):
    blocks = {}
    for i in range(0, len(old) - 15, 8):
        key = old[i:i + 16]
        positions = blocks.setdefault(key, [])
        if len(positions) < 16:
            positions.append(i)
    ops, literal = [], bytearray()
    pos = 0
    while pos < len(new):
        best, start = 0, 0
        for candidate in blocks.get(new[pos:pos + 16], []):
            length = 16
            while (candidate + length < len(old) and pos + length < len(new)
                   and old[candidate + length] == new[pos + length]):
                length += 1
            if length > best:
                best, start = length, candidate
        if best >= 24:
            if literal:
                ops.append(base64.b64encode(literal).decode('ascii'))
                literal.clear()
            ops.append([start, best])
            pos += best
        else:
            literal.append(new[pos])
            pos += 1
    if literal:
        ops.append(base64.b64encode(literal).decode('ascii'))
    return ops


def build(original, translated, destination):
    entries = []
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(translated) as target:
        for name in target.namelist():
            old = source.read(name) if name in source.namelist() else b''
            new = target.read(name)
            if old != new:
                entries.append(dict(nombre=name,
                                    original=sha(old) if name in source.namelist() else None,
                                    traducido=sha(new), longitud=len(new),
                                    operaciones=delta(old, new)))
        if set(source.namelist()) - set(target.namelist()):
            raise ValueError('El generador no admite eliminar entradas del juego.')
    payload = dict(formato=1, version='0.9.8', steam_appid=856570,
                   build_referencia='22743398', entradas=entries)
    Path(destination).write_text(json.dumps(payload, ensure_ascii=True, separators=(',', ':')),
                                 encoding='utf-8')
    print(f'{len(entries)} entradas; {Path(destination).stat().st_size:,} bytes')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('original')
    p.add_argument('traducido')
    p.add_argument('salida')
    a = p.parse_args()
    build(a.original, a.traducido, a.salida)
