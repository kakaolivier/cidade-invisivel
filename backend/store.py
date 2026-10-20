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
