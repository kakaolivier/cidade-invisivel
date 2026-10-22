import json
import os
import sys
import tempfile
from pathlib import Path
import subprocess
import time
import httpx
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
tmp=tempfile.TemporaryDirectory()
shots=root/'work'/'browser-checks'
shots.mkdir(parents=True,exist_ok=True)
env={**os.environ,'DATA_DIR':tmp.name,'PORT':'8001'}
proc=subprocess.Popen([sys.executable,'run.py'],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for i in range(50):
        try:
            if httpx.get('http://127.0.0.1:8001/api/projects').status_code==200: break
        except httpx.HTTPError: pass
        time.sleep(.1)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.getenv('BROWSER_EXECUTABLE'),headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader'])
        page=browser.new_page(viewport={'width':1512,'height':982})
        errors=[];external=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:external.append(req.url) if req.url.startswith('http') and not req.url.startswith('http://127.0.0.1:8001') else None)
        page.goto('http://127.0.0.1:8001',wait_until='networkidle')
        page.wait_for_function("document.getElementById('status').textContent.includes('13 elementos')")
        page.screenshot(path=str(shots/'interface-2d.png'))
        page.wait_for_function('!map.isMoving() && map.isSourceLoaded("network")')
        # Testa clique real no mapa, sem chamar select diretamente.
        xy=page.evaluate("""()=>{const f=state.data.features.find(f=>f.properties.standard.id==='TR-003');const c=f.geometry.coordinates;const pos=map.project([(c[0][0]+c[1][0])/2,(c[0][1]+c[1][1])/2]);const r=document.getElementById('map').getBoundingClientRect();return [r.x+pos.x,r.y+pos.y];}""")
        page.mouse.click(*xy)
        page.wait_for_function("document.getElementById('selectionTitle').textContent==='TR-003'")
        page.locator('#traceBtn').click()
        page.wait_for_function("document.getElementById('analysis').textContent.includes('3 trechos')")
        page.wait_for_timeout(200)
        assert page.evaluate("map.getSource('particle')._data.type")=='Feature'
        before=page.evaluate("map.getSource('particle')._data.geometry.coordinates")
        page.wait_for_timeout(350)
        assert page.evaluate("map.getSource('particle')._data.geometry.coordinates")!=before
        assert page.locator('#animationInfo').is_visible()
        page.locator('#stopBtn').click()
        page.locator('#scenarioBtn').click()
        page.wait_for_function("document.getElementById('analysis').textContent.includes('montante')")
        page.locator('#mode3').click()
        page.wait_for_function("state.viewer!==null && state.mode==='3d'",timeout=60000)
        page.wait_for_timeout(1500)
        page.evaluate("document.querySelector('.right').scrollTop=0")
        page.screenshot(path=str(shots/'interface-3d.png'))
        assert page.evaluate('state.viewer.entities.values.length')==13
        assert page.locator('#mapNotice').is_visible()
        page.locator('#mode2').click()
        page.locator('#importBtn').click()
        geo={'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'LineString','coordinates':[[-49.3,-25.4],[-49.301,-25.401]]},'properties':{'id':'REAL-01','material':'PEAD','diameter':200,'extra':'original'}}]}
        page.locator('#file').set_input_files({'name':'rede.geojson','mimeType':'application/geo+json','buffer':json.dumps(geo).encode()})
        page.locator('#uploadForm button[type=submit]').click()
        page.wait_for_selector('#mapping:visible')
        page.locator('#commitBtn').click()
        page.wait_for_function("document.getElementById('status').textContent.includes('1 elementos')")
        assert page.locator('#banner').inner_text().startswith('PROJETO REAL')
        await_detail=page.evaluate("select(state.data.features[0].id)")
        assert page.evaluate("feature(state.selected).properties.original.extra")=='original'
        real=page.evaluate('state.project')
        page.reload(wait_until='networkidle')
        page.wait_for_function("document.getElementById('status').textContent.includes('13 elementos')")
        page.locator('#projects').select_option(real)
        page.wait_for_function("document.getElementById('status').textContent.includes('1 elementos')")
        page.locator('#diameter').select_option('200')
        page.wait_for_function("document.getElementById('status').textContent.includes('filtrado')")
        assert page.evaluate('state.data.count')==1
        page.locator('#projects').select_option('demo')
        page.wait_for_function("document.getElementById('status').textContent.includes('13 elementos')")
        assert errors==[],errors
        assert external==[],external
        print(json.dumps({'page_errors':errors,'external_requests':external,'checks':['2D','clique real','atributos','percurso animado','interrupcao','3D 13 feicoes','importacao por formulario','persistencia apos recarregar','filtros','isolamento demo/real']}))
        browser.close()
finally:
    proc.terminate();proc.wait(timeout=10);tmp.cleanup()
