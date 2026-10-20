"""Baixa distribuições prontas e licenças; nenhuma ferramenta Node é usada."""
import io
import tarfile
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'frontend'/'vendor'
ROOT.mkdir(parents=True,exist_ok=True)
def get(url):
    print('Obtendo',url)
    with urllib.request.urlopen(url,timeout=120) as r: return r.read()
for name in ('maplibre-gl.js','maplibre-gl.css'):
    (ROOT/name).write_bytes(get('https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/'+name))
(ROOT/'MAPLIBRE-LICENSE.txt').write_bytes(get('https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/LICENSE.txt'))
raw=get('https://registry.npmjs.org/cesium/-/cesium-1.121.0.tgz')
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:
    for member in tar.getmembers():
        prefix='package/Build/Cesium/'
        if member.isfile() and member.name.startswith(prefix):
            rel=Path(member.name[len(prefix):]); dest=(ROOT/'cesium'/rel).resolve()
            if not dest.is_relative_to((ROOT/'cesium').resolve()): raise ValueError('Caminho inválido')
            dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(tar.extractfile(member).read())
    for name in ('LICENSE.md','ThirdParty.extra.json'):
        try: (ROOT/('CESIUM-'+name)).write_bytes(tar.extractfile('package/'+name).read())
        except KeyError: pass
print('Bibliotecas locais prontas. O aplicativo pode abrir sem internet.')
