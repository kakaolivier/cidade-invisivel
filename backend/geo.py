"""Importação, normalização e preservação dos atributos geográficos."""
import io
import json
import math
import tempfile
import zipfile
from pathlib import Path
from pyproj import CRS, Transformer, Geod
from shapely.geometry import shape, mapping
from shapely import transform

FIELDS = {
 'id':['id','objectid','fid','codigo'], 'diameter':['diametro','diameter','dn'],
 'material':['material','mat'], 'depth':['profundidade','depth'],
 'up_elevation':['cota_montante','up_elevation'], 'down_elevation':['cota_jusante','down_elevation'],
 'surface_elevation':['cota_tampa','surface_elevation'], 'bottom_elevation':['cota_fundo','bottom_elevation'],
 'kind':['tipo','kind','tipo_rede'], 'status':['situacao','status'],
 'from_node':['pv_inicial','from_node','no_montante'], 'to_node':['pv_final','to_node','no_jusante']}
GEOD = Geod(ellps='WGS84')

def suggestions(fields):
    lower = {x.casefold():x for x in fields}
    return {key:next((lower[a] for a in aliases if a in lower), '') for key,aliases in FIELDS.items()}

def read_file(data, filename, source_crs=None, layer=None):
    suffix = Path(filename).suffix.lower()
    if suffix in ('.json','.geojson'):
        obj = json.loads(data)
        if obj.get('type') != 'FeatureCollection':
            raise ValueError('Envie um GeoJSON FeatureCollection.')
        crs = source_crs or obj.get('crs',{}).get('properties',{}).get('name')
        # RFC 7946: GeoJSON sem membro crs usa longitude/latitude WGS84.
        crs = crs or 'EPSG:4326'
        return obj['features'], crs, ['GeoJSON RFC 7946: WGS84 quando não há SRC explícito.']
    if suffix not in ('.zip','.gpkg'):
        raise ValueError('Formato aceito: GeoJSON, Shapefile ZIP ou GeoPackage.')
    try:
        import fiona
    except ImportError:
        raise ValueError('Para ZIP/GPKG, instale: python -m pip install -r requirements-gis.txt') from None
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        if suffix == '.zip':
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if len(z.infolist()) > 1000 or sum(x.file_size for x in z.infolist()) > 200*1024*1024:
                    raise ValueError('ZIP excede o limite descompactado (200 MB/1000 arquivos).')
                for info in z.infolist():
                    path = (base/info.filename).resolve()
                    if not path.is_relative_to(base.resolve()):
                        raise ValueError('Caminho inseguro no ZIP.')
                z.extractall(base)
            files = list(base.rglob('*.shp')) + list(base.rglob('*.SHP'))
            if layer:
                files = [f for f in files if f.stem == layer]
            if len(files) != 1:
                raise ValueError('Selecione uma camada em layer. Camadas: '+', '.join(f.stem for f in files))
            path = files[0]
            if not path.with_suffix('.dbf').exists() or not path.with_suffix('.shx').exists():
                raise ValueError('Shapefile requer .shp, .shx e .dbf; inclua .prj ou selecione o SRC.')
            selected = None
        else:
            path = base/'upload.gpkg'; path.write_bytes(data)
            layers = fiona.listlayers(path)
            if len(layers)>1 and not layer:
                raise ValueError('Informe layer. Camadas GeoPackage: '+', '.join(layers))
            selected = layer or layers[0]
        with fiona.open(path, layer=selected) as src:
            crs = source_crs or src.crs_wkt or src.crs
            if not crs:
                raise ValueError('SRC ausente: selecione EPSG:31982, 4674, 4326 ou outro SRC conhecido.')
            features = [{'type':'Feature','geometry':fiona.model.to_dict(f.geometry) if f.geometry else None,
                         'properties':dict(f.properties)} for f in src]
            return features, CRS(crs).to_string(), []

def normalize(features, source_crs, field_map, layer_kind):
    if len(features)>100000: raise ValueError('Limite de 100.000 feições por importação.')
    transformer = Transformer.from_crs(source_crs,4326,always_xy=True)
    result=[]
    for index, feature in enumerate(features):
        if not feature.get('geometry'): raise ValueError(f'Feição {index+1} sem geometria.')
        original_geometry=feature['geometry']; geom=shape(original_geometry)
        if geom.is_empty or not geom.is_valid: raise ValueError(f'Geometria inválida na feição {index+1}.')
        if geom.geom_type not in ('LineString','MultiLineString','Point','MultiPoint','Polygon','MultiPolygon'):
            raise ValueError('Tipo de geometria não suportado: '+geom.geom_type)
        geom = transform(geom,transformer.transform,interleaved=False,include_z=None)
        if not all(math.isfinite(v) for v in geom.bounds) or not (-180<=geom.bounds[0]<=geom.bounds[2]<=180 and -90<=geom.bounds[1]<=geom.bounds[3]<=90):
            raise ValueError('Coordenadas fora da faixa geográfica. Confira o SRC de origem.')
        props=feature.get('properties') or {}
        standard={key:props.get(value) for key,value in field_map.items() if key in FIELDS and value}
        standard['id']=str(standard.get('id') if standard.get('id') is not None else index+1)
        standard['length_m']=abs(GEOD.geometry_length(geom)) if 'LineString' in geom.geom_type else 0
        result.append({'type':'Feature','geometry':mapping(geom),'properties':{'original':props,'standard':standard},
                       'original_geometry':original_geometry,'layer_kind':layer_kind})
    if not result: raise ValueError('Camada sem feições.')
    return result
