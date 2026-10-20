from .geo import normalize

def seed(store):
    if any(p['id']=='demo' for p in store.projects()): return
    store.create_project('Laboratório • rede sintética',True,'demo')
    points={'PV-01':[-49.278,-25.432],'PV-02':[-49.275,-25.432], 'PV-03':[-49.272,-25.433],
            'PV-04':[-49.269,-25.434],'PV-05':[-49.275,-25.429],'PV-06':[-49.272,-25.436], 'PV-07':[-49.266,-25.435]}
    links=[('PV-01','PV-02'),('PV-05','PV-02'),('PV-02','PV-03'),('PV-06','PV-03'),('PV-03','PV-04'),('PV-04','PV-07')]
    fs=[]
    for i,(a,b) in enumerate(links):
        fs.append({'type':'Feature','geometry':{'type':'LineString','coordinates':[points[a],points[b]]},
          'properties':{'id':f'TR-{i+1:03}','from_node':a,'to_node':b,'diameter':150 if i<4 else 300,'material':'PVC' if i<4 else 'Concreto','kind':'Coletora','status':'Demonstração'}})
    fields={k:k for k in ('id','from_node','to_node','diameter','material','kind','status')}
    store.add_layer('demo','Rede sintética','collector','EPSG:4326','Não informado',fields,normalize(fs,4326,fields,'collector'))
    fs=[{'type':'Feature','geometry':{'type':'Point','coordinates':coord},'properties':{'id':key}} for key,coord in points.items()]
    store.add_layer('demo','Poços sintéticos','manhole','EPSG:4326','Não informado',{'id':'id'},normalize(fs,4326,{'id':'id'},'manhole'))
