# Armazenamento

A aplicação cria o esquema transacional em `backend/store.py`.

- `projects`: projetos separados e marca de demonstração.
- `layers`: projeto, categoria, SRC original, referência vertical, mapeamento e metadados da fonte.
- `features`: geometria normalizada para WGS84, geometria original e atributos originais/padronizados em JSON.
- PostGIS: coluna `geom` com SRC 4326, dimensões 2D/3D preservadas e índice espacial GiST.
- SQLite: índice RTree das caixas envolventes. A consulta local por área usa interseção das caixas, podendo incluir feições próximas sem interseção exata.

Nenhum banco é exposto pela aplicação como arquivo estático. Dados ficam em `data/` (ou `DATA_DIR`). O ZIP de entrega não contém banco de dados privado. Dados de demonstração são criados na primeira execução.

Para PostGIS de produção, peça ao administrador para provisionar a extensão. O usuário em execução deve ter só as permissões necessárias; a criação inicial de esquema e extensão deve ser revisada e realizada na fase de implantação. O adaptador atual inicializa o esquema na partida, adequado ao uso local, não é um gerenciador completo de migrações.
