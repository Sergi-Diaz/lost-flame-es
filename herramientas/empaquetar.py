import hashlib
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
dist = root / 'dist'
dist.mkdir(exist_ok=True)
out = dist / 'LostFlame-es-0.9.8.zip'
files = [root / name for name in ['Instalar.cmd', 'Instalar.ps1', 'instalar.py', 'README.md', 'parche/parche.json']]
files.extend(sorted((root / 'traduccion').glob('*.json')))
with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in files:
        z.write(p, 'LostFlame-es-0.9.8/' + p.relative_to(root).as_posix())
digest = hashlib.sha256(out.read_bytes()).hexdigest()
(dist / 'SHA256SUMS.txt').write_text(digest + '  ' + out.name + '\n', encoding='ascii')
print(str(out) + ': ' + str(out.stat().st_size) + ' bytes')
