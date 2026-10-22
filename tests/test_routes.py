import pytest
from fastapi.testclient import TestClient
from backend.geo import normalize
from backend.topology import Topology
from backend.routing import RoutingService
from backend.store import Store
from backend.demo import seed

@pytest.fixture
def api(tmp_path,monkeypatch):
    monkeypatch.setenv('DATA_DIR',str(tmp_path));monkeypatch.delenv('DATABASE_URL',raising=False)
    from backend import main
    store=Store();seed(store)
    monkeypatch.setattr(main,'store',store);monkeypatch.setattr(main,'routing',RoutingService(store))
    return TestClient(main.app),store

def ids(client):
    return {f['properties']['standard']['id']:f['id'] for f in client.get('/api/projects/demo/features').json()['features']}

def test_demo_route_is_ordered_and_bounded(api):
    client,_=api;id=ids(client)
    r=client.post('/api/projects/demo/route',json={'start':id['TR-003']})
    assert r.status_code==200
    route=r.json();assert route['directed'] and len(route['steps'])==3
    assert route['automatic_destination'] and route['end_label']=='PV-07'
    lookup={f['id']:f for f in route['features']}
    end=None
    for step in route['steps']:
        coords=lookup[step['id']]['geometry']['coordinates']
        if step['reverse']:coords=list(reversed(coords))
        if end is not None:assert coords[0]==end
        end=coords[-1]

def test_directed_route_rejects_upstream_and_disconnected(api):
    client,_=api;id=ids(client)
    assert client.post('/api/projects/demo/route',json={'start':id['PV-07'],'end':id['PV-01']}).status_code==400
    assert client.post('/api/projects/demo/route',json={'start':id['PV-01'],'end':id['PV-07']}).status_code==200
    assert client.post('/api/projects/demo/route',json={'start':id['PV-01'],'end':id['PV-01']}).status_code==400

def test_geometry_codes_are_not_hydraulic_direction_and_old_mapping_works(api):
    client,store=api;project=store.create_project('Sintético')
    points=[[-49,-25],[-49.001,-25],[-49.002,-25],[-49.01,-25]]
    fs=[{'type':'Feature','geometry':{'type':'Point','coordinates':c},'properties':{'GlobalID':f'GUID-{i}','GEOCODIGO':f'PV-{i}'}} for i,c in enumerate(points)]
    store.add_layer(project,'PVs','manhole',4326,'Não informado',{'id':'GlobalID'},normalize(fs,4326,{'id':'GlobalID'},'manhole'))
    lines=[{'type':'Feature','geometry':{'type':'LineString','coordinates':points[i:i+2]},'properties':{'PV_INICIO':f'PV-{i}','PV_FINAL':f'PV-{i+1}'}} for i in (0,1)]
    mapping={'from_node':'PV_INICIO','to_node':'PV_FINAL'}
    store.add_layer(project,'Linhas','collector',4326,'Não informado',mapping,normalize(lines,4326,mapping,'collector'))
    choices=client.get(f'/api/projects/{project}/route/choices?q=PV-').json()
    id={x['label']:x['id'] for x in choices}
    r=client.post(f'/api/projects/{project}/route',json={'start':id['PV-2'],'end':id['PV-0']})
    assert r.status_code==200,r.text
    data=r.json();assert len(data['steps'])==2 and data['illustrative'] and not data['directed']
    assert all(s['reverse'] for s in data['steps'])
    disconnected=client.post(f'/api/projects/{project}/route',json={'start':id['PV-3']})
    assert disconnected.status_code==400 and 'sem conexão' in disconnected.json()['detail']
    detail=client.get(f'/api/projects/{project}/feature/{id["PV-0"]}').json()
    assert detail['properties']['standard']['id']=='GUID-0' # cadastro preservado
    assert detail['properties']['original']['GEOCODIGO']=='PV-0'

def test_compact_map_preserves_detail_and_project_isolation(api):
    client,store=api;id=ids(client)
    data=client.get('/api/projects/demo/features?compact=true').json()
    assert data['count']==13 and all(f['properties']['original'] is None for f in data['features'])
    detail=client.get(f'/api/projects/demo/feature/{id["TR-001"]}').json()
    assert detail['properties']['original']['material']=='PVC'
    other=store.create_project('Outro')
    assert client.get(f'/api/projects/{other}/feature/{id["TR-001"]}').status_code==400

def test_parallel_records_do_not_make_animation_visit_entire_component():
    fs=[]
    for i in range(40):
        fs.append({'id':str(i),'geometry':{'type':'LineString','coordinates':[[-49,-25],[-49.001,-25]]},'properties':{'standard':{'start_node':'A','end_node':'B','length_m':100}}})
    fs.append({'id':'last','geometry':{'type':'LineString','coordinates':[[-49.001,-25],[-49.002,-25]]},'properties':{'standard':{'start_node':'B','end_node':'C','length_m':100}}})
    graph=Topology(fs,.5);route=graph.route('0')
    assert route['component_count']==41 and len(route['steps'])==2
    assert route['length_m']==200 and route['illustrative']

def test_route_limit_and_cache_invalidation(api):
    client,store=api
    from backend import main
    graph=main.routing.graph('demo');old=graph
    id=ids(client)
    with pytest.raises(ValueError,match='máximo'):
        graph.route(id['PV-01'],id['PV-07'],max_steps=1)
    fs=[{'type':'Feature','geometry':{'type':'Point','coordinates':[-49.5,-25.5]},'properties':{'id':'NEW'}}]
    store.add_layer('demo','Nova camada','manhole',4326,'Não informado',{'id':'id'},normalize(fs,4326,{'id':'id'},'manhole'))
    assert main.routing.graph('demo') is not old
