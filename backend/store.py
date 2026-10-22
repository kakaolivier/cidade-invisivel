"""SQLite local com RTree; PostGIS opcional com GiST e geometrias originais."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from shapely.geometry import shape

class Store:
    def __init__(self):
        self.url=os.getenv('DATABASE_URL','')
        self.pg=bool(self.url)
        self.path=Path(os.getenv('DATA_DIR','data'))/'cidade.sqlite3'
        if not self.pg: self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as con:
            if self.pg:
                con.execute('CREATE EXTENSION IF NOT EXISTS postgis')
                con.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, demo BOOLEAN)')
                con.execute('CREATE TABLE IF NOT EXISTS layers (id TEXT PRIMARY KEY, project TEXT REFERENCES projects(id), name TEXT, kind TEXT, crs TEXT, vertical_ref TEXT, field_map TEXT)')
                con.execute('CREATE TABLE IF NOT EXISTS features (id TEXT PRIMARY KEY, layer TEXT REFERENCES layers(id), body TEXT, geom geometry CHECK (ST_SRID(geom)=4326))')
                con.execute('CREATE INDEX IF NOT EXISTS features_geom_gist ON features USING GIST(geom)')
                con.execute('CREATE INDEX IF NOT EXISTS features_layer ON features(layer)')
            else:
                con.executescript('''CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT,demo BOOLEAN);
CREATE TABLE IF NOT EXISTS layers(id TEXT PRIMARY KEY,project TEXT REFERENCES projects(id),name TEXT,kind TEXT,crs TEXT,vertical_ref TEXT,field_map TEXT);
CREATE TABLE IF NOT EXISTS features(rowid INTEGER PRIMARY KEY,id TEXT UNIQUE,layer TEXT REFERENCES layers(id),body TEXT);
CREATE INDEX IF NOT EXISTS features_layer ON features(layer);
CREATE VIRTUAL TABLE IF NOT EXISTS feature_bounds USING rtree(id,minx,maxx,miny,maxy);''')
            if self.pg:
                con.execute('ALTER TABLE layers ADD COLUMN IF NOT EXISTS source_metadata TEXT')
            elif 'source_metadata' not in [r[1] for r in con.execute('PRAGMA table_info(layers)')]:
                con.execute('ALTER TABLE layers ADD COLUMN source_metadata TEXT')
    @contextmanager
    def connect(self):
        if self.pg:
            import psycopg
            from psycopg.rows import dict_row
            con=psycopg.connect(self.url,row_factory=dict_row)
        else:
            con=sqlite3.connect(self.path); con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON')
        try:
            yield con; con.commit()
        except Exception:
            con.rollback(); raise
        finally: con.close()
    def sql(self,s): return s.replace('?','%s') if self.pg else s
    def rows(self,sql,args=()):
        with self.connect() as c: return [dict(r) for r in c.execute(self.sql(sql),args).fetchall()]
    def projects(self): return self.rows('SELECT * FROM projects ORDER BY demo DESC,name')
    def project(self,id):
        rows=self.rows('SELECT * FROM projects WHERE id=?',(id,))
        if not rows: raise ValueError('Projeto não encontrado.')
        return rows[0]
    def create_project(self,name,demo=False,id=None):
        id=id or uuid4().hex
        with self.connect() as c: c.execute(self.sql('INSERT INTO projects VALUES(?,?,?)'),(id,name,demo))
        return id
    def layers(self,project): return self.rows('SELECT * FROM layers WHERE project=?',(project,))
    def add_layer(self,project,name,kind,crs,vertical_ref,field_map,features,source_metadata=None):
        self.project(project)
        layer=uuid4().hex
        with self.connect() as c:
            c.execute(self.sql('INSERT INTO layers(id,project,name,kind,crs,vertical_ref,field_map,source_metadata) VALUES(?,?,?,?,?,?,?,?)'),(layer,project,name,kind,str(crs),vertical_ref,json.dumps(field_map),json.dumps(source_metadata or {})))
            for f in features:
                fid=uuid4().hex; f['id']=fid; f['layer']=layer; f['layer_kind']=kind
                if self.pg:
                    c.execute('INSERT INTO features VALUES(%s,%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))',(fid,layer,json.dumps(f),json.dumps(f['geometry'])))
                else:
                    cur=c.execute('INSERT INTO features(id,layer,body) VALUES(?,?,?)',(fid,layer,json.dumps(f)))
                    x,y,xx,yy=shape(f['geometry']).bounds
                    c.execute('INSERT INTO feature_bounds VALUES(?,?,?,?,?)',(cur.lastrowid,x,xx,y,yy))
        return layer
    def features(self,project,bbox=None):
        sql='SELECT f.body FROM features f JOIN layers l ON l.id=f.layer '
        args=[project]
        if bbox and not self.pg: sql+='JOIN feature_bounds b ON b.id=f.rowid '
        sql+='WHERE l.project=?'
        if bbox:
            x,y,xx,yy=bbox
            if self.pg:
                sql+=' AND ST_Intersects(f.geom,ST_MakeEnvelope(?,?,?,?,4326))'; args += [x,y,xx,yy]
            else:
                sql+=' AND b.maxx>=? AND b.minx<=? AND b.maxy>=? AND b.miny<=?'; args += [x,xx,y,yy]
        return [json.loads(r['body']) for r in self.rows(sql,args)]

    def features_by_ids(self,project,ids):
        if not ids: return []
        result=[]
        for offset in range(0,len(ids),400):
            chunk=ids[offset:offset+400]
            query='SELECT f.body FROM features f JOIN layers l ON l.id=f.layer WHERE l.project=? AND f.id IN ('+','.join('?' for _ in chunk)+')'
            result.extend(json.loads(r['body']) for r in self.rows(query,[project,*chunk]))
        return result

    def routing_features(self,project):
        """Projeção leve: não transfere os atributos originais de toda a base."""
        if self.pg:
            query="""SELECT f.id,f.layer,l.kind,l.field_map,
                f.body::jsonb->'geometry' AS geometry,
                f.body::jsonb#>'{properties,standard}' AS standard,
                f.body::jsonb#>>'{properties,original,GEOCODIGO}' AS pv_code,
                f.body::jsonb#>>'{properties,original,PV_INICIO}' AS start_code,
                f.body::jsonb#>>'{properties,original,PV_FINAL}' AS end_code
                FROM features f JOIN layers l ON l.id=f.layer WHERE l.project=?"""
        else:
            query="""SELECT f.id,f.layer,l.kind,l.field_map,
                json_extract(f.body,'$.geometry') AS geometry,
                json_extract(f.body,'$.properties.standard') AS standard,
                json_extract(f.body,'$.properties.original.GEOCODIGO') AS pv_code,
                json_extract(f.body,'$.properties.original.PV_INICIO') AS start_code,
                json_extract(f.body,'$.properties.original.PV_FINAL') AS end_code
                FROM features f JOIN layers l ON l.id=f.layer WHERE l.project=?"""
        result=[]
        for row in self.rows(query,(project,)):
            geometry=row['geometry'] if isinstance(row['geometry'],dict) else json.loads(row['geometry'])
            standard=dict(row['standard']) if isinstance(row['standard'],dict) else json.loads(row['standard'])
            field_map=json.loads(row['field_map']);known=True
            if geometry['type']=='Point' and row['pv_code']:
                standard['node_id']=str(row['pv_code'])
            if geometry['type']=='LineString':
                if not standard.get('start_node') and row['start_code']: standard['start_node']=str(row['start_code'])
                if not standard.get('end_node') and row['end_code']: standard['end_node']=str(row['end_code'])
                # Campos de início/fim geométrico de importações antigas não
                # certificam direção hidráulica, mesmo mapeados como from/to.
                if str(field_map.get('from_node','')).casefold() in ('pv_inicio','pv_inicial') or str(field_map.get('to_node','')).casefold()=='pv_final':
                    known=False
            result.append({'type':'Feature','id':row['id'],'layer':row['layer'],'layer_kind':row['kind'],
                'geometry':geometry,'properties':{'standard':standard,'original':None},'direction_known':known,'_compact':True})
        return result
