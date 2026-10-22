"""Conector restrito a camadas configuradas no servidor. Token nunca vai ao cliente."""
import json
import os
import re
import httpx
from .config import MAX_FEATURES

def sources():
    return json.loads(os.getenv('ARCGIS_SOURCES','{}'))

def fetch(alias):
    config=sources().get(alias)
    if not config: raise ValueError('Fonte ArcGIS não autorizada no servidor.')
    url=config['url'].rstrip('/')
    if not re.fullmatch(r'https://[^/?#@]+/[^?#]*/FeatureServer/\d+',url):
        raise ValueError('Configure URL HTTPS de uma camada FeatureServer/N, sem query ou credenciais.')
    token=os.getenv(config.get('token_env','ARCGIS_TOKEN'),'')
    with httpx.Client(timeout=45,follow_redirects=False) as client:
        def call(path,params):
            payload={'f':'json',**params}
            if token: payload['token']=token
            try:
                r=client.post(url+path,data=payload); r.raise_for_status(); obj=r.json()
            except (httpx.HTTPError,ValueError):
                raise ValueError('Falha de acesso ao ArcGIS. Confira URL, acesso de rede e autenticação no servidor; importe por arquivo como alternativa.') from None
            if 'error' in obj: raise ValueError('ArcGIS recusou a consulta. Verifique permissões e token no servidor; use importação por arquivo.')
            return obj
        meta=call('',{})
        ids=call('/query',{'where':'1=1','returnIdsOnly':'true'}).get('objectIds')
        if ids is None: raise ValueError('Serviço não retornou IDs para paginação segura.')
        if len(ids)>MAX_FEATURES: raise ValueError(f'Fonte excede {MAX_FEATURES:,} feições (MAX_FEATURES); divida a importação.')
        batch=min(int(meta.get('maxRecordCount',1000)),1000); features=[]; seen=set()
        for start in range(0,len(ids),batch):
            chunk=ids[start:start+batch]
            obj=call('/query',{'objectIds':','.join(map(str,chunk)),'outFields':'*','returnGeometry':'true','outSR':'4326','returnZ':'true'})
            if obj.get('exceededTransferLimit'): raise ValueError('Limite do serviço atingido; reduza maxRecordCount no conector.')
            oid=meta.get('objectIdField','OBJECTID')
            for item in obj.get('features',[]):
                attrs=item.get('attributes',{}); key=attrs.get(oid)
                if key is None or key in seen: raise ValueError('IDs ausentes ou repetidos na resposta ArcGIS.')
                seen.add(key); geom=item.get('geometry',{})
                if 'paths' in geom:
                    paths=geom['paths']; geometry={'type':'LineString','coordinates':paths[0]} if len(paths)==1 else {'type':'MultiLineString','coordinates':paths}
                elif 'x' in geom: geometry={'type':'Point','coordinates':[geom['x'],geom['y']]+([geom['z']] if 'z' in geom else [])}
                else: raise ValueError('Conector atual suporta pontos e linhas ArcGIS; exporte polígonos para GeoJSON/GPKG.')
                features.append({'type':'Feature','geometry':geometry,'properties':attrs})
        if len(features)!=len(ids): raise ValueError('Resposta ArcGIS incompleta. Nenhuma camada foi salva.')
        return features,meta
