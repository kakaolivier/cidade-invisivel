"""Cache limitado a um projeto/tolerância e percursos com geometrias de resposta."""
from threading import RLock
from .topology import Topology

class RoutingService:
    def __init__(self,store):
        self.store=store;self._lock=RLock();self._key=None;self._graph=None;self._features={}
    def graph(self,project,tolerance=.5):
        if not 0<=tolerance<=20: raise ValueError('Tolerância deve estar entre 0 e 20 metros.')
        self.store.project(project)
        key=(project,float(tolerance),tuple(sorted(layer['id'] for layer in self.store.layers(project))))
        with self._lock:
            if key!=self._key:
                fs=self.store.routing_features(project)
                self._graph=Topology(fs,tolerance);self._features={f['id']:f for f in fs};self._key=key
            return self._graph
    def choices(self,project,q='',tolerance=.5):
        with self._lock:
            graph=self.graph(project,tolerance);q=q.strip().casefold();items=[]
            for f in self._features.values():
                if f['geometry']['type']!='Point': continue
                s=f['properties']['standard'];label=str(s.get('node_id') or s.get('id') or f['id'])
                if q and q not in label.casefold(): continue
                items.append({'id':f['id'],'label':label,'connected':bool(graph.points.get(f['id']))})
                if len(items)==25: break
            return items
    def route(self,project,start,end=None,tolerance=.5):
        with self._lock:
            graph=self.graph(project,tolerance);result=graph.route(start,end)
            ids=list(dict.fromkeys([*result['ids'],start,*([end] if end else [])]))
            result['features']=self.store.features_by_ids(project,ids)
            labels={node:f['properties']['standard'].get('node_id') or f['properties']['standard'].get('id')
                for f in self._features.values() if f['geometry']['type']=='Point'
                for node in graph.points.get(f['id'],[])}
            result['start_label']=str(labels.get(result['start_node']) or result['start_node'].removeprefix('id:'))
            result['end_label']=str(labels.get(result['end_node']) or result['end_node'].removeprefix('id:'))
            return result
