"""Um processo serve API e interface. Não requer Node."""
import os
from pathlib import Path
os.chdir(Path(__file__).resolve().parent)
if __name__=='__main__':
    if not (Path('frontend/vendor/maplibre-gl.js').is_file() and Path('frontend/vendor/cesium/Cesium.js').is_file()):
        raise SystemExit('Bibliotecas de mapas ausentes. Execute: python scripts/download_assets.py')
    import uvicorn
    host=os.getenv('HOST','127.0.0.1')
    if host not in ('127.0.0.1','localhost','::1') and not os.getenv('APP_PASSWORD'):
        raise SystemExit('Para expor o servidor, configure APP_PASSWORD e HTTPS via proxy. Leia o README.')
    uvicorn.run('backend.main:app',host=host,port=int(os.getenv('PORT','8000')),access_log=False)
