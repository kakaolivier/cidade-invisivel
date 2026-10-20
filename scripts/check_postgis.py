"""Teste opcional contra um PostGIS descartável. Usa DATABASE_URL do processo."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.store import Store
from backend.geo import normalize
store=Store()
assert store.pg, 'Configure DATABASE_URL para um banco descartável.'
project=store.create_project('Teste de persistência PostGIS')
f={'type':'Feature','geometry':{'type':'LineString','coordinates':[[-49,-25,10],[-49.001,-25,9]]},'properties':{'ID':'PG-01','extra':'original'}}
fs=normalize([f],4326,{'id':'ID'},'collector')
store.add_layer(project,'Rede teste','collector','EPSG:4326','Teste',{'id':'ID'},fs)
loaded=store.features(project,[-50,-26,-48,-24])
assert len(loaded)==1 and loaded[0]['original_geometry']==f['geometry']
with store.connect() as con:
    row=con.execute('SELECT ST_SRID(geom) AS srid, ST_NDims(geom) AS dims FROM features WHERE id=%s',(loaded[0]['id'],)).fetchone()
    assert row['srid']==4326 and row['dims']==3
    assert con.execute("SELECT indexname FROM pg_indexes WHERE indexname='features_geom_gist'").fetchone()
    con.execute('DELETE FROM features WHERE layer IN (SELECT id FROM layers WHERE project=%s)',(project,))
    con.execute('DELETE FROM layers WHERE project=%s',(project,))
    con.execute('DELETE FROM projects WHERE id=%s',(project,))
print('PostGIS OK: persistência, atributos, consulta espacial, SRID 4326, Z e índice GiST.')
