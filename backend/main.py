import json
import os
import secrets
from collections import Counter
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .store import Store
from .geo import read_file, normalize, suggestions, FIELDS
from .topology import Topology
from .demo import seed
from .arcgis import sources, fetch
from .config import MAX_FEATURES, MAX_UPLOAD_MB
from .routing import RoutingService

ROOT=Path(__file__).resolve().parent.parent
MAX_BYTES=MAX_UPLOAD_MB*1024*1024
KINDS={'collector','interceptor','outfall','manhole','pump','treatment','basin','district','streets','terrain'}
store=Store(); seed(store)
routing=RoutingService(store)
app=FastAPI(title='Cidade Invisível',version='1.0.0')
# Dados temporários ficam no disco privado, não em URLs públicas.
STAGING=Path(os.getenv('DATA_DIR','data'))/'staging'; STAGING.mkdir(parents=True,exist_ok=True)
for old in STAGING.glob('*.json'): old.unlink(missing_ok=True)

@app.middleware('http')
async def local_security(request:Request,call_next):
    token=os.getenv('APP_PASSWORD','')
    if token and request.url.path.startswith('/api/') and not secrets.compare_digest(request.headers.get('authorization','').encode(),('Bearer '+token).encode()):
        return JSONResponse({'detail':'Senha de acesso necessária.'},401)
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail':'Origem não permitida.'},403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    # OSM requer Referer. Requisições externas recebem só a origem, sem caminho/atributos.
    response.headers['Referrer-Policy']='no-referrer' if request.url.path.startswith('/api/') else 'strict-origin-when-cross-origin'
    if request.url.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
    return response

@app.exception_handler(ValueError)
async def bad_value(request,error): return JSONResponse({'detail':str(error)},400)

@app.exception_handler(Exception)
async def unexpected(request,error):
    # Não expor URLs, SQL, atributos ou tokens em respostas e logs.
    return JSONResponse({'detail':'Falha interna. Confira o formato dos dados e a configuração do servidor.'},500)

class ProjectInput(BaseModel): name:str=Field(min_length=1,max_length=100)
class CommitInput(BaseModel):
    project:str; name:str=Field(min_length=1,max_length=100); kind:str='collector'
    field_map:dict[str,str]={}; vertical_ref:str='Não informado'
class TraceInput(BaseModel): selected:str; tolerance:float=Field(default=0.5,ge=0,le=20); scenario:bool=False
class RouteInput(BaseModel):
    start:str; end:str|None=None; tolerance:float=Field(default=0.5,ge=0,le=20)

@app.get('/api/projects')
def projects(): return {'projects':store.projects(),'storage':'PostGIS' if store.pg else 'SQLite + índice RTree'}
@app.post('/api/projects')
def project_create(body:ProjectInput): return {'id':store.create_project(body.name)}
@app.get('/api/projects/{project}/layers')
def layers(project:str):
    store.project(project); return store.layers(project)

def filtered(project,q='',material='',diameter='',kind='',bbox=None,compact=False):
    data=store.routing_features(project) if compact and not q and bbox is None else store.features(project,bbox)
    def match(f):
        s=f['properties']['standard']
        return (not q or q.casefold() in json.dumps(f['properties'],ensure_ascii=False).casefold()) and (not material or str(s.get('material',''))==material) and (not diameter or str(s.get('diameter',''))==diameter) and (not kind or f['layer_kind']==kind)
    return [f for f in data if match(f)]

@app.get('/api/projects/{project}/features')
def features(project:str,q:str='',material:str='',diameter:str='',kind:str='',bbox:str='',compact:bool=False):
    store.project(project)
    bounds=None
    if bbox:
        try: bounds=list(map(float,bbox.split(','))); assert len(bounds)==4 and bounds[0]<=bounds[2] and bounds[1]<=bounds[3]
        except (ValueError,AssertionError): raise ValueError('bbox inválida: xmin,ymin,xmax,ymax.')
    data=filtered(project,q,material,diameter,kind,bounds,compact)
    if compact:
        data=[{**{k:v for k,v in f.items() if k!='original_geometry'},'properties':{'standard':f['properties']['standard'],'original':None},'_compact':True} for f in data]
    return {'type':'FeatureCollection','features':data,'count':len(data)}

@app.get('/api/projects/{project}/indicators')
def indicators(project:str,q:str='',material:str='',diameter:str='',kind:str=''):
    fs=filtered(project,q,material,diameter,kind,compact=True)
    lines=[f for f in fs if 'LineString' in f['geometry']['type']]
    def group(key): return dict(Counter(str(f['properties']['standard'].get(key) if f['properties']['standard'].get(key) is not None else 'Não informado') for f in lines))
    return {'scope':'filtrado' if any((q,material,diameter,kind)) else 'toda a base','length_m':sum(f['properties']['standard'].get('length_m',0) for f in lines),
        'pipes':len(lines),'manholes':sum(f['layer_kind']=='manhole' for f in fs),'pumps':sum(f['layer_kind']=='pump' for f in fs),'treatments':sum(f['layer_kind']=='treatment' for f in fs),
        'incomplete':sum(any(f['properties']['standard'].get(k) is None for k in ('diameter','material','depth')) for f in lines),
        'materials':group('material'),'diameters':group('diameter'),'total':len(fs)}

@app.post('/api/import/preview')
async def preview(file:UploadFile=File(...),source_crs:str=Form(''),layer:str=Form('')):
    parts=[]; size=0
    while chunk:=await file.read(1024*1024):
        size+=len(chunk)
        if size>MAX_BYTES: raise HTTPException(413,'Arquivo excede limite de upload.')
        parts.append(chunk)
    try: fs,crs,warnings=read_file(b''.join(parts),file.filename or '',source_crs or None,layer or None)
    except (ValueError,KeyError,TypeError,OSError) as ex: raise ValueError(str(ex)) from None
    return stage(fs,crs,warnings)

def stage(fs,crs,warnings):
    if not fs or len(fs)>MAX_FEATURES: raise ValueError(f'A importação deve ter entre 1 e {MAX_FEATURES:,} feições (MAX_FEATURES).')
    # Valida coordenadas antes de criar a prévia.
    normalize(fs,crs,{},'collector')
    import time
    for item in STAGING.glob('*.json'):
        if time.time()-item.stat().st_mtime>3600: item.unlink(missing_ok=True)
    if sum(p.stat().st_size for p in STAGING.glob('*.json'))>300*1024*1024: raise ValueError('Área temporária cheia. Reinicie o servidor para limpar.')
    ticket=uuid4().hex
    fields=sorted({k for f in fs for k in (f.get('properties') or {})})
    (STAGING/(ticket+'.json')).write_text(json.dumps({'features':fs,'crs':str(crs)}),encoding='utf-8')
    return {'ticket':ticket,'count':len(fs),'crs':str(crs),'fields':fields,'suggestions':suggestions(fields),'warnings':warnings,'sample':fs[0].get('properties',{})}

@app.post('/api/import/{ticket}/commit')
def commit(ticket:str,body:CommitInput):
    if len(ticket)!=32 or not all(x in '0123456789abcdef' for x in ticket): raise ValueError('Importação inválida.')
    path=STAGING/(ticket+'.json')
    if not path.exists(): raise ValueError('Prévia expirada. Envie o arquivo novamente.')
    if store.project(body.project)['demo']: raise ValueError('Crie um projeto real: demonstração é separada.')
    if body.kind not in KINDS: raise ValueError('Tipo de camada inválido.')
    data=json.loads(path.read_text(encoding='utf-8'))
    fs=normalize(data['features'],data['crs'],body.field_map,body.kind)
    id=store.add_layer(body.project,body.name,body.kind,data['crs'],body.vertical_ref,body.field_map,fs,data.get('arcgis_metadata',{}))
    path.unlink(missing_ok=True)
    return {'layer':id,'count':len(fs)}

@app.get('/api/arcgis/sources')
def arc_sources(): return [{'id':key,'name':value.get('name',key)} for key,value in sources().items()]
@app.post('/api/arcgis/{alias}/preview')
def arc_preview(alias:str):
    fs,meta=fetch(alias)
    result=stage(fs,'EPSG:4326',['ArcGIS reprojetado para WGS84 pelo serviço; metadados preservados no arquivo da prévia.'])
    path=STAGING/(result['ticket']+'.json'); data=json.loads(path.read_text()); data['arcgis_metadata']=meta; path.write_text(json.dumps(data))
    # Metadados sem tokens armazenados posteriormente em cada camada (referência original).
    result['source_spatial_reference']=meta.get('extent',{}).get('spatialReference')
    return result
@app.post('/api/projects/{project}/trace')
def trace(project:str,body:TraceInput): return routing.graph(project,body.tolerance).trace(body.selected,body.scenario)
@app.get('/api/projects/{project}/topology')
def topology(project:str,tolerance:float=0.5): return routing.graph(project,tolerance).report()

@app.post('/api/projects/{project}/route')
def route(project:str,body:RouteInput): return routing.route(project,body.start,body.end,body.tolerance)
@app.get('/api/projects/{project}/route/choices')
def route_choices(project:str,q:str='',tolerance:float=.5): return routing.choices(project,q,tolerance)
@app.get('/api/projects/{project}/feature/{fid}')
def feature_detail(project:str,fid:str):
    data=store.features_by_ids(project,[fid])
    if not data: raise ValueError('Elemento não encontrado neste projeto.')
    return data[0]

@app.get('/')
def index(): return FileResponse(ROOT/'frontend/index.html')
app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')
