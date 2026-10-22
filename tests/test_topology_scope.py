"""Regressão: uma ambiguidade distante não deve contaminar outro componente."""
from pyproj import Transformer
from backend.geo import normalize
from backend.topology import Topology

def graph_with_distant_ambiguity():
    tx=Transformer.from_crs(31982,4326,always_xy=True)
    lines=[[(0,0),(10,0)],[(100,0),(110,0)],[(110.8,0),(120,0)],[(110.4,0),(130,0)]]
    fs=[{'type':'Feature','geometry':{'type':'LineString','coordinates':[tx.transform(680000+x,8140000+y) for x,y in coords]},'properties':{}} for coords in lines]
    data=normalize(fs,4326,{},'collector')
    for i,f in enumerate(data):f['id']=str(i)
    return Topology(data,.5)

def test_distant_ambiguity_excluded_from_trace_and_scenario():
    graph=graph_with_distant_ambiguity()
    assert len(graph.ambiguities)==1
    for scenario in (False,True):
        result=graph.trace('0',scenario)
        assert result['ids']==['0']
        assert result['ambiguities']==[]
        assert result['global_ambiguity_count']==1
        assert result['ambiguities_scope']=='connected_component'
    assert len(graph.report()['ambiguities'])==1

def test_refused_connection_warns_both_candidate_components():
    graph=graph_with_distant_ambiguity()
    # O trecho 3 não foi unido aos nós próximos, mas o alerta é relevante
    # tanto para ele quanto para os dois componentes candidatos 1 e 2.
    for selected in ('1','2','3'):
        result=graph.trace(selected)
        assert len(result['ambiguities'])==1
        assert result['global_ambiguity_count']==1
