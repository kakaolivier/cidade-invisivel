import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

_temp=tempfile.TemporaryDirectory()
os.environ['DATA_DIR']=_temp.name
os.environ.pop('DATABASE_URL',None)
from backend.main import app,store
from backend.geo import normalize, read_file, suggestions
from backend.topology import Topology
from pyproj import Transformer
client=TestClient(app)

def line(coords=None,props=None):
    return {'type':'Feature','geometry':{'type':'LineString','coordinates':coords or [[-49,-25],[-49.001,-25]]},'properties':props or {'id':'R1','material':'PVC'}}

def upload(fs,**extra):
    return client.post('/api/import/preview',files={'file':('rede.geojson',json.dumps({'type':'FeatureCollection','features':fs}),'application/json')},data=extra)

def test_demo_and_endpoints():
    p=client.get('/api/projects').json(); assert p['projects'][0]['demo']
    data=client.get('/api/projects/demo/features').json(); assert len(data['features'])==13
    indicators=client.get('/api/projects/demo/indicators').json()
    assert indicators['pipes']==6 and indicators['manholes']==7 and indicators['length_m']>1000
    assert client.get('/').status_code==200
    assert client.get('/api/projects/demo/layers').status_code==200

def test_mapping_and_persistence():
    project=client.post('/api/projects',json={'name':'Real'}).json()['id']
    fs=[line(props={'COD':'T-01','DN':200,'campo_extra':'preservado'})]
    p=upload(fs).json(); assert p['suggestions']['diameter']=='DN'
    r=client.post(f"/api/import/{p['ticket']}/commit",json={'project':project,'name':'Rede','field_map':{'id':'COD','diameter':'DN'},'kind':'collector'})
    assert r.status_code==200
    imported=client.get(f'/api/projects/{project}/features').json()['features'][0]
    assert imported['properties']['original']['campo_extra']=='preservado'
    assert imported['properties']['standard']['diameter']==200
    assert imported['original_geometry']==fs[0]['geometry']
    assert store.features(project)[0]['id']==imported['id']

def test_crs_31982_4674():
    for code in (31982,4674):
        transform=Transformer.from_crs(4326,code,always_xy=True)
        coords=[list(transform.transform(-49,-25)),list(transform.transform(-49.001,-25))]
        data=normalize([line(coords)],code,{},'collector')
        assert data[0]['geometry']['coordinates'][0][0]==pytest.approx(-49,abs=1e-7)
        assert 100<data[0]['properties']['standard']['length_m']<102

def test_undirected_not_digitization():
    data=normalize([line(),line([[-49.001,-25],[-49.002,-25]])],4326,{},'collector')
    for i,f in enumerate(data): f['id']=str(i)
    graph=Topology(data,0.5); trace=graph.trace('0'); assert trace['ids']==['0','1']; assert not trace['directed']
    assert graph.report()['count']==2

def test_directed_branching_and_scenario():
    fs=client.get('/api/projects/demo/features').json()['features']
    id={f['properties']['standard']['id']:f['id'] for f in fs}
    r=client.post('/api/projects/demo/trace',json={'selected':id['TR-003']}).json()
    assert r['directed'] and len(r['ids'])==3
    r=client.post('/api/projects/demo/trace',json={'selected':id['TR-003'],'scenario':True}).json()
    assert len(r['ids'])==3 and id['TR-001'] in r['ids'] and id['TR-004'] not in r['ids']
    pv=client.post('/api/projects/demo/trace',json={'selected':id['PV-03']}).json()
    assert len(pv['ids'])==2

def test_filters_and_spatial_index():
    r=client.get('/api/projects/demo/indicators?material=PVC').json()
    assert r['pipes']==4 and r['scope']=='filtrado'
    assert client.get('/api/projects/demo/features?bbox=0,0,1,1').json()['count']==0
    assert client.get('/api/projects/demo/features?bbox=1,2,0,0').status_code==400
    assert client.get('/api/projects/demo/topology?tolerance=-1').status_code==400

def test_errors_security_and_isolation(monkeypatch):
    assert upload([line([[500000,7000000],[500001,7000001]])]).status_code==400
    p=upload([line()]).json()
    assert client.post(f"/api/import/{p['ticket']}/commit",json={'project':'demo','name':'x'}).status_code==400
    assert client.post('/api/arcgis/unknown/preview').status_code==400
    assert client.post('/api/projects',json={'name':'X'},headers={'origin':'https://attacker.example'}).status_code==403
    monkeypatch.setenv('APP_PASSWORD','secret')
    assert client.get('/api/projects').status_code==401
    assert client.get('/api/projects',headers={'Authorization':'Bearer secret'}).status_code==200

def test_zip_traversal_rejected():
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z: z.writestr('../evil.shp',b'X')
    with pytest.raises(ValueError,match='inseguro'): read_file(buf.getvalue(),'rede.zip')

def test_shapefile_zip_and_geopackage(tmp_path):
    import fiona
    schema={'geometry':'LineString','properties':{'COD':'str','DN':'int'}}
    coords=line()['geometry']
    for driver,suffix in [('ESRI Shapefile','.shp'),('GPKG','.gpkg')]:
        path=tmp_path/('rede'+suffix)
        with fiona.open(path,'w',driver=driver,schema=schema,crs='EPSG:4326') as dst:
            dst.write({'geometry':coords,'properties':{'COD':'A','DN':150}})
        if suffix=='.shp':
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w') as z:
                for f in tmp_path.glob('rede.*'): z.write(f,f.name)
            raw=buf.getvalue();name='rede.zip'
        else: raw=path.read_bytes();name='rede.gpkg'
        fs,crs,_=read_file(raw,name); data=normalize(fs,crs,{'id':'COD','diameter':'DN'},'collector')
        assert data[0]['properties']['standard']['diameter']==150

def test_missing_crs_shapefile(tmp_path):
    import fiona
    path=tmp_path/'no_crs.shp'
    with fiona.open(path,'w',driver='ESRI Shapefile',schema={'geometry':'LineString','properties':{'id':'str'}}) as dst:
        dst.write(line(props={'id':'R1'}))
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        for f in tmp_path.glob('*'): z.write(f,f.name)
    with pytest.raises(ValueError,match='SRC ausente'): read_file(buf.getvalue(),'no_crs.zip')

def test_topology_tolerance_meters():
    fs=[line(),line([[-49.001004,-25],[-49.002,-25]])]
    data=normalize(fs,4326,{},'collector')
    for i,f in enumerate(data):f['id']=str(i)
    assert len(Topology(data,.5).trace('0')['ids'])==2
    assert len(Topology(data,.1).trace('0')['ids'])==1

def test_arcgis_batches_token_and_metadata(monkeypatch):
    import backend.arcgis as arc
    requests=[]
    monkeypatch.setenv('ARCGIS_SOURCES',json.dumps({'rede':{'url':'https://gis.example.org/server/rest/services/Rede/FeatureServer/0','token_env':'TEST_ARC_TOKEN'}}))
    monkeypatch.setenv('TEST_ARC_TOKEN','private-token')
    class Response:
        def __init__(self,obj): self.obj=obj
        def raise_for_status(self): pass
        def json(self): return self.obj
    class Client:
        def __init__(self,**kwargs): assert kwargs['follow_redirects'] is False
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,data):
            requests.append((url,data))
            if not url.endswith('/query'):return Response({'maxRecordCount':1,'objectIdField':'OBJECTID','extent':{'spatialReference':{'wkid':31982}}})
            if data.get('returnIdsOnly'): return Response({'objectIds':[1,2]})
            key=int(data['objectIds'])
            return Response({'features':[{'attributes':{'OBJECTID':key},'geometry':{'x':-49,'y':-25}}]})
    monkeypatch.setattr(arc.httpx,'Client',Client)
    fs,meta=arc.fetch('rede')
    assert len(fs)==2 and len(requests)==4
    assert all(req[1]['token']=='private-token' for req in requests)
    public=client.get('/api/arcgis/sources').json()
    assert 'private-token' not in json.dumps(public) and public[0]['id']=='rede'
    p=client.post('/api/arcgis/rede/preview').json()
    project=store.create_project('ArcGIS teste')
    r=client.post(f"/api/import/{p['ticket']}/commit",json={'project':project,'name':'Rede','kind':'manhole'})
    assert r.status_code==200
    metadata=json.loads(store.layers(project)[0]['source_metadata'])
    assert metadata['extent']['spatialReference']['wkid']==31982

def test_3d_coordinates_preserved():
    f=line([[-49,-25,10],[-49.001,-25,9]])
    fs=normalize([f],4326,{},'collector')
    assert fs[0]['geometry']['coordinates'][0][2]==10

def test_ambiguous_endpoints_reported():
    fs=[line([[-49,-25],[-49.001,-25]]),line([[-49.001008,-25],[-49.002,-25]]),line([[-49.001004,-25],[-49.003,-25]])]
    data=normalize(fs,4326,{},'collector')
    for i,f in enumerate(data):f['id']=str(i)
    graph=Topology(data,.5)
    assert graph.ambiguities
