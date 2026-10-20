"""Grafo local projetado. Direção somente por IDs montante/jusante declarados."""
import math
from collections import defaultdict, deque
from pyproj import CRS, Transformer
from shapely.geometry import shape

class Topology:
    def __init__(self,features,tolerance=0.5):
        if not 0<=tolerance<=20: raise ValueError('Tolerância deve estar entre 0 e 20 metros.')
        self.tolerance=tolerance; self.edges={}; self.inc=defaultdict(list); self.points={}; self.ambiguities=[]
        lines=[f for f in features if f['geometry']['type']=='LineString']
        coords=[f['geometry']['coordinates'][0] for f in lines]
        lon=sum(c[0] for c in coords)/len(coords) if coords else 0
        lat=sum(c[1] for c in coords)/len(coords) if coords else 0
        # AEQD local: unidade metro, sem presumir uma zona UTM para toda a base.
        self.crs=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m').to_string()
        tx=Transformer.from_crs(4326,self.crs,always_xy=True)
        cells=defaultdict(list); named={}; endpoint_id=0
        def node(coord, explicit):
            nonlocal endpoint_id
            x,y=tx.transform(*coord[:2]); cellsize=max(tolerance,0.000001); cell=(math.floor(x/cellsize),math.floor(y/cellsize))
            if explicit is not None and str(explicit)!='':
                key='id:'+str(explicit)
                if key in named and math.dist(named[key],(x,y))>max(tolerance,0.01): self.ambiguities.append('ID de nó com posições divergentes: '+str(explicit))
                named[key]=(x,y); return key
            matches=[]
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for key,px,py in cells[(cell[0]+dx,cell[1]+dy)]:
                        if math.hypot(px-x,py-y)<=tolerance: matches.append(key)
            if len(matches)>1:
                self.ambiguities.append('Extremidade próxima de múltiplos nós: mantida separada.')
            if len(matches)==1: return matches[0]
            endpoint_id+=1; key='xy:'+str(endpoint_id); cells[cell].append((key,x,y)); return key
        # Nós explícitos não são fundidos com inferidos: evita presumir relação entre IDs e geometria.
        for f in lines:
            s=f['properties']['standard']; coords=f['geometry']['coordinates']
            a=node(coords[0],s.get('from_node')); b=node(coords[-1],s.get('to_node'))
            directed=bool(s.get('from_node') is not None and s.get('to_node') is not None and str(s.get('from_node')) and str(s.get('to_node')))
            self.edges[f['id']]=(a,b,directed); self.inc[a].append(f['id']); self.inc[b].append(f['id'])
        for f in features:
            if f['geometry']['type']=='Point':
                s=f['properties']['standard']; key='id:'+str(s.get('id'))
                if key in self.inc: self.points[f['id']]=[key]
                else:
                    x,y=tx.transform(*f['geometry']['coordinates'][:2]); candidates=[]
                    for key2, lst in cells.items():
                        if abs(key2[0]-math.floor(x/max(tolerance,1e-6)))<=1 and abs(key2[1]-math.floor(y/max(tolerance,1e-6)))<=1:
                            candidates += [k for k,px,py in lst if math.hypot(px-x,py-y)<=tolerance]
                    self.points[f['id']]=candidates
        self.unsupported=sum(f['geometry']['type']=='MultiLineString' for f in features)
    def trace(self,selected,scenario=False):
        if selected not in self.edges and selected not in self.points: raise ValueError('Selecione uma linha simples ou um PV.')
        # Um componente com qualquer aresta sem direção confiável é explorado sem direção.
        starts=list(self.edges[selected][:2]) if selected in self.edges else self.points[selected]
        component=set(); queue=deque(starts); visited=set(starts)
        while queue:
            n=queue.popleft()
            for eid in self.inc[n]:
                component.add(eid)
                a,b,_=self.edges[eid]
                for nxt in (a,b):
                    if nxt not in visited: visited.add(nxt); queue.append(nxt)
        directed=bool(component) and all(self.edges[e][2] for e in component)
        seed=list(self.edges[selected][:2]) if selected in self.edges else starts
        if directed and selected in self.edges: seed=[self.edges[selected][0 if scenario else 1]]
        queue=deque(seed); seen=set(seed); result=[selected] if selected in self.edges else []; steps=[]
        used=set(result)
        while queue:
            n=queue.popleft()
            for eid in self.inc[n]:
                if eid in used or (scenario and eid==selected): continue
                a,b,_=self.edges[eid]
                if directed and ((scenario and n!=b) or (not scenario and n!=a)): continue
                nxt=a if n==b else b; used.add(eid); result.append(eid)
                steps.append({'id':eid,'reverse':n==b})
                if nxt not in seen: seen.add(nxt); queue.append(nxt)
        if selected in self.edges: steps.insert(0,{'id':selected,'reverse':False})
        return {'ids':result,'steps':steps,'directed':directed,'tolerance_m':self.tolerance,'crs':self.crs,
                'message':('Cenário: trechos a montante potencialmente relacionados.' if scenario else 'Percurso dirigido pelas declarações de montante/jusante.') if directed else 'Conectividade não dirigida; sentido hidráulico desconhecido. Conjunto relacionado, sem previsão hidráulica.',
                'ambiguities':self.ambiguities,'unsupported_multilines':self.unsupported}
    def report(self):
        ends=[{'node':n,'feature':e[0]} for n,e in self.inc.items() if len(e)==1]
        return {'apparent_endpoints':ends,'count':len(ends),'ambiguities':self.ambiguities,'tolerance_m':self.tolerance,'crs':self.crs,'unsupported_multilines':self.unsupported,
                'note':'Extremidades são indícios para revisão; incluem inícios e saídas legítimos. Interseções no meio de linhas não são divididas automaticamente.'}
