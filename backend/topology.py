"""Grafo local projetado. Direção somente por IDs montante/jusante declarados."""
import math
import heapq
from collections import defaultdict, deque
from pyproj import CRS, Transformer
from shapely.geometry import shape

class Topology:
    def __init__(self,features,tolerance=0.5):
        if not 0<=tolerance<=20: raise ValueError('Tolerância deve estar entre 0 e 20 metros.')
        self.tolerance=tolerance; self.edges={}; self.inc=defaultdict(list); self.points={}; self.ambiguities=[]
        self._ambiguity_context=[]
        self.weights={}; self.node_positions={}
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
                if key in named and math.dist(named[key],(x,y))>max(tolerance,0.01):
                    self.ambiguities.append('ID de nó com posições divergentes: '+str(explicit))
                    self._ambiguity_context.append((f['id'],[key]))
                named[key]=(x,y); return key
            matches=[]
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for key,px,py in cells[(cell[0]+dx,cell[1]+dy)]:
                        if math.hypot(px-x,py-y)<=tolerance: matches.append(key)
            if len(matches)>1:
                self.ambiguities.append('Extremidade próxima de múltiplos nós: mantida separada.')
                self._ambiguity_context.append((f['id'],list(matches)))
            if len(matches)==1: return matches[0]
            endpoint_id+=1; key='xy:'+str(endpoint_id); cells[cell].append((key,x,y)); return key
        # Nós explícitos não são fundidos com inferidos: evita presumir relação entre IDs e geometria.
        for f in lines:
            s=f['properties']['standard']; coords=f['geometry']['coordinates']
            a=node(coords[0],s.get('start_node') or s.get('from_node')); b=node(coords[-1],s.get('end_node') or s.get('to_node'))
            self.node_positions.setdefault(a,coords[0]); self.node_positions.setdefault(b,coords[-1])
            length=s.get('length_m')
            if not isinstance(length,(int,float)) or not math.isfinite(length) or length<=0:
                from .geo import GEOD
                length=abs(GEOD.line_length([c[0] for c in coords],[c[1] for c in coords]))
            self.weights[f['id']]=max(float(length),1e-6)
            directed=bool(s.get('from_node') is not None and s.get('to_node') is not None and str(s.get('from_node')) and str(s.get('to_node')) and f.get('direction_known',True))
            self.edges[f['id']]=(a,b,directed); self.inc[a].append(f['id']); self.inc[b].append(f['id'])
        for f in features:
            if f['geometry']['type']=='Point':
                s=f['properties']['standard']; key='id:'+str(s.get('node_id') or s.get('id'))
                if key in self.inc: self.points[f['id']]=[key]
                else:
                    x,y=tx.transform(*f['geometry']['coordinates'][:2]); candidates=[]
                    cx=math.floor(x/max(tolerance,1e-6));cy=math.floor(y/max(tolerance,1e-6))
                    for dx in (-1,0,1):
                        for dy in (-1,0,1):
                            candidates += [k for k,px,py in cells.get((cx+dx,cy+dy),[]) if math.hypot(px-x,py-y)<=tolerance]
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
        # Inclui o trecho que gerou o alerta e componentes tocados pelos nós
        # candidatos, mesmo quando a união ambígua foi recusada.
        component_ambiguities=[message for message,(eid,nodes) in zip(self.ambiguities,self._ambiguity_context)
            if eid in component or any(edge in component for node in nodes for edge in self.inc[node])]
        return {'ids':result,'steps':steps,'directed':directed,'tolerance_m':self.tolerance,'crs':self.crs,
                'message':('Cenário: trechos a montante potencialmente relacionados.' if scenario else 'Percurso dirigido pelas declarações de montante/jusante.') if directed else 'Conectividade não dirigida; sentido hidráulico desconhecido. Conjunto relacionado, sem previsão hidráulica.',
                'ambiguities':component_ambiguities,'global_ambiguity_count':len(self.ambiguities),
                'ambiguities_scope':'connected_component','unsupported_multilines':self.unsupported}
    def route(self,start,end=None,max_steps=500):
        """Menor percurso métrico; destino automático ilustrativo quando omitido."""
        def nodes(fid):
            if fid in self.edges: return [self.edges[fid][0]]
            if fid in self.points:
                found=self.points[fid]
                if not found: raise ValueError('PV sem conexão conhecida na tolerância atual. Escolha outro PV e confira o identificador GEOCODIGO.')
                if len(found)>1: raise ValueError('PV associado a múltiplos nós; selecione um trecho ou outro PV sem ambiguidade.')
                return found
            raise ValueError('Elemento não encontrado na rede. Selecione uma linha simples ou um PV.')
        if start==end: raise ValueError('Escolha origem e destino diferentes ou deixe o destino automático.')
        origin=nodes(start)[0]
        targets=set(nodes(end)) if end else set()
        if end in self.edges: targets=set(self.edges[end][:2])
        component=set(); visited={origin}; queue=deque([origin])
        while queue:
            n=queue.popleft()
            for eid in self.inc[n]:
                component.add(eid)
                for nxt in self.edges[eid][:2]:
                    if nxt not in visited: visited.add(nxt);queue.append(nxt)
        if not component: raise ValueError('Não há tubulações conectadas a este elemento.')
        directed=all(self.edges[e][2] for e in component)
        distances={origin:0.0};previous={};hops={origin:0};heap=[(0.0,origin)]
        while heap:
            distance,n=heapq.heappop(heap)
            if distance!=distances[n]: continue
            if targets and n in targets: break
            for eid in self.inc[n]:
                a,b,_=self.edges[eid]
                if directed and n!=a: continue
                nxt=b if n==a else a
                if nxt==n: continue
                candidate=distance+self.weights[eid]
                if candidate<distances.get(nxt,math.inf):
                    distances[nxt]=candidate;previous[nxt]=(n,eid,n==b);hops[nxt]=hops[n]+1
                    heapq.heappush(heap,(candidate,nxt))
        if targets:
            reachable=[n for n in targets if n in distances and (n!=origin or len(targets)==1)]
            if not reachable: raise ValueError('Não existe percurso conectado entre os elementos com a topologia e direção conhecidas. Confira os PVs e a tolerância.')
            destination=min(reachable,key=distances.get)
        else:
            candidates=[n for n in distances if n!=origin and hops[n]<=max_steps]
            if not candidates: raise ValueError('Nenhum percurso disponível a partir desta origem. Experimente outro PV.')
            known=[n for n in candidates if n.startswith('id:')]
            destination=max(known or candidates,key=lambda n:(distances[n],n))
        steps=[];current=destination
        while current!=origin:
            parent,eid,reverse=previous[current]
            steps.append({'id':eid,'reverse':reverse});current=parent
        steps.reverse()
        if not steps: raise ValueError('Origem e destino correspondem ao mesmo nó. Escolha outro destino.')
        if len(steps)>max_steps: raise ValueError(f'O percurso tem {len(steps)} trechos; escolha um destino mais próximo (máximo {max_steps}).')
        ambiguities=[message for message,(eid,candidates) in zip(self.ambiguities,self._ambiguity_context)
            if eid in component or any(edge in component for node in candidates for edge in self.inc[node])]
        return {'type':'route','ids':[s['id'] for s in steps],'steps':steps,'directed':directed,'illustrative':not directed,
                'length_m':sum(self.weights[s['id']] for s in steps),'automatic_destination':end is None,
                'start_node':origin,'end_node':destination,'start_coordinate':self.node_positions[origin],
                'end_coordinate':self.node_positions[destination],'component_count':len(component),
                'ambiguities':ambiguities,'global_ambiguity_count':len(self.ambiguities),'tolerance_m':self.tolerance,
                'message':'Percurso pela direção declarada no cadastro; sem previsão hidráulica.' if directed else 'PERCURSO ILUSTRATIVO DE CONECTIVIDADE — sentido hidráulico desconhecido.'}

    def report(self):
        ends=[{'node':n,'feature':e[0]} for n,e in self.inc.items() if len(e)==1]
        return {'apparent_endpoints':ends,'count':len(ends),'ambiguities':self.ambiguities,'tolerance_m':self.tolerance,'crs':self.crs,'unsupported_multilines':self.unsupported,
                'note':'Extremidades são indícios para revisão; incluem inícios e saídas legítimos. Interseções no meio de linhas não são divididas automaticamente.'}
