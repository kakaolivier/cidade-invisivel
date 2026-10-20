import json,os,subprocess,tempfile,time,sys,zlib,struct
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
shots=root/'work'/'basemap-checks';shots.mkdir(parents=True,exist_ok=True)
# PNG sintético: valida o transporte/renderização, sem acessar o OSM real.
def chunk(kind,data):
    return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
rows=b''.join(b'\x00'+b''.join(bytes((255,255,255) if x%64<8 or y%64<8 else (230,230,223)) for x in range(256)) for y in range(256))
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',256,256,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')
with tempfile.TemporaryDirectory() as tmp:
    env={**os.environ,'DATA_DIR':tmp,'PORT':'8003'}
    env.pop('DATABASE_URL',None);env.pop('APP_PASSWORD',None)
    proc=subprocess.Popen([sys.executable,'run.py'],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                r=httpx.get('http://127.0.0.1:8003/');r.raise_for_status();break
            except httpx.HTTPError:time.sleep(.1)
        assert r.headers['referrer-policy']=='strict-origin-when-cross-origin'
        assert httpx.get('http://127.0.0.1:8003/api/projects').headers['referrer-policy']=='no-referrer'
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.getenv('BROWSER_EXECUTABLE'),headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader'])
            page=browser.new_page(viewport={'width':1512,'height':982});requests=[];errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def tile(route):
                req=route.request;requests.append({'url':req.url,'referer':req.all_headers().get('referer')})
                route.fulfill(status=200,content_type='image/png',body=png,headers={'access-control-allow-origin':'*','cache-control':'public,max-age=3600'})
            page.route('https://tile.openstreetmap.org/**',tile)
            page.goto('http://127.0.0.1:8003',wait_until='networkidle')
            page.wait_for_function("state.data.count===13 && !map.isMoving()")
            assert not requests,'Mapa-base não deve ser pedido antes da ativação.'
            page.locator('#basemapBtn').click()
            page.wait_for_function("map.getLayer('osm') && map.isSourceLoaded('osm')")
            page.wait_for_timeout(500)
            assert requests and all(x['referer']=='http://127.0.0.1:8003/' for x in requests),requests
            assert page.evaluate("map.getPaintProperty('osm','raster-opacity')")==.85
            assert page.evaluate("map.getLayoutProperty('osm','visibility')")=='visible'
            if not page.get_by_role('link',name='OpenStreetMap',exact=True).is_visible():
                page.locator('.maplibregl-ctrl-attrib-button').click()
            assert page.get_by_role('link',name='OpenStreetMap',exact=True).is_visible()
            page.screenshot(path=str(shots/'osm-2d-tiles-simulados.png'))
            page.locator('#mode3').click()
            page.wait_for_function("state.osm3d && state.osm3d.show")
            page.wait_for_timeout(1500)
            assert page.evaluate('state.viewer.entities.values.length')==13
            assert page.evaluate("map.getLayoutProperty('osm','visibility')")=='none'
            page.locator('#basemapBtn').click()
            assert page.evaluate('state.osm3d.show') is False
            page.locator('#mode2').click()
            assert page.evaluate("map.getLayoutProperty('osm','visibility')")=='none'
            # Simula falha de tiles para verificar o aviso ao usuário.
            page.unroute('https://tile.openstreetmap.org/**',tile)
            page.route('https://tile.openstreetmap.org/**',lambda route:route.fulfill(status=403,body='Blocked',headers={'access-control-allow-origin':'*'}))
            page.evaluate("map.removeLayer('osm');map.removeSource('osm')")
            page.locator('#basemapBtn').click()
            page.wait_for_function('state.basemapFailed===true')
            assert 'OpenStreetMap: falha' in page.locator('#toast').inner_text()
            assert errors==[],errors
            print(json.dumps({'page_errors':errors,'tile_requests_mocked':len(requests),'referer_origin_only':True,'checks':['inicialmente desligado','2D tiles + opacidade','atribuicao','3D provider + 13 feicoes','alternancia 2D/3D','desligar','aviso 403','cabecalhos da interface e API']}))
            browser.close()
    finally:proc.terminate();proc.wait(timeout=10)
