# CIDADE INVISÍVEL

**Explore o que existe sob seus pés.**

Aplicação SIG local executável: backend Python/FastAPI, mapa MapLibre, visualização Cesium, importação geográfica, persistência e análise topológica. Não precisa de Node, Java, compilação de frontend ou token de mapas. O navegador executa JavaScript pronto, obtido pelo script Python incluído no projeto. Não é necessário instalar ferramentas JavaScript.

## Início rápido — recomendado para máquina limitada

Requisitos: **Python 3.12 ou superior, 64 bits**, navegador recente com WebGL e aceleração gráfica. Testado com Python 3.12 e Chromium. Para máquinas antigas, comece pelo 2D. A instalação de pacotes requer internet; a operação básica depois da instalação usa arquivos locais.

Extraia o ZIP, abra um terminal **dentro da pasta `cidade-invisivel`** e execute:

### Windows

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-gis.txt
.venv\Scripts\python scripts\download_assets.py
.venv\Scripts\python run.py
```

### Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-gis.txt
.venv/bin/python scripts/download_assets.py
.venv/bin/python run.py
```

Abra **http://127.0.0.1:8000**. Pare com `Ctrl+C`. Não há processo separado para frontend: o FastAPI serve interface, bibliotecas e API na mesma porta.

Se quiser a instalação mínima, use `requirements.txt`: GeoJSON, SQLite, mapas, indicadores e topologia funcionam. `requirements-gis.txt` acrescenta Fiona (Shapefile/GPKG) e psycopg (PostGIS). Os pacotes de processamento são binários; não é necessário instalar GDAL à parte quando há wheel compatível. Se o pip tentar compilar, confira Python 3.12 64 bits e a disponibilidade de wheel para seu sistema.

O modo local usa **SQLite com RTree**, já incluído no Python. Não requer servidor de banco nem Docker. Os dados persistem em `data/cidade.sqlite3`. O projeto não realiza publicação automática.

As distribuições prontas de MapLibre 4.7.1 e Cesium 1.121.0 são baixadas para `frontend/vendor/`, junto com as licenças. O download do repositório GitHub contém o código do projeto; execute este passo uma vez para obter as bibliotecas de mapas, como indicado nos comandos acima:

```bash
python scripts/download_assets.py
```

O download usa só Python, cerca de 21 MB descompactados. Depois do primeiro download, não precisa ser repetido. O mapa-base externo está desligado por padrão; o fundo sem ruas é intencional, a rede continua georreferenciada. O botão de mapa-base ativa OpenStreetMap, com atribuição visível. Respeite a política https://operations.osmfoundation.org/policies/tiles/ ; não faça download em massa. Essa opção envia pedidos de tiles da área visualizada a terceiros. Não a ative com dados sensíveis sem autorização. Sem internet, mantenha-a desligada.

## O que está implementado

- Demonstração sintética isolada: seis trechos e sete PVs, com sentido explicitamente declarado, sem cotas inventadas.
- Projetos e múltiplas camadas persistentes. A importação não altera a demonstração.
- Mapa 2D com zoom, pan, enquadramento, seleção, consulta de atributos, camadas, opacidade e destaque.
- Pesquisa textual em atributos, filtros por material, diâmetro e categoria, medição aproximada e consulta de área retangular.
- Importação com prévia, amostra de atributos e mapeamento manual/assistido de campos.
- GeoJSON, Shapefile ZIP e GeoPackage; reprojeção com PyProj (31982, 4674, 4326 e outros SRCs reconhecidos).
- Geometrias originais e todos os atributos preservados no banco, além da geometria WGS84 usada pelo mapa. Não são sobrescritos por simplificação cartográfica.
- Cesium local, navegação, inclinação/rotação, seleção, globo translúcido e profundidade simbólica configurável. Espessura visual em pixels relacionada ao diâmetro, sem afirmar escala volumétrica real.
- Conectividade de linhas simples e PVs, tolerância métrica configurável, extremidades de grau 1 e sinalização de ambiguidades.
- Percurso animado, parar/reiniciar e velocidade. Em ramificações, a animação apresenta os trechos em ordem de exploração do grafo e pode saltar de um ramo para outro; não é uma partícula hidráulica contínua.
- Interrupção hipotética reversível: relações a montante quando o componente é dirigido; conjunto relacionado quando não há direção confiável.
- Indicadores reais e filtrados: extensão geodésica, trechos, PVs, elevatórias, ETEs, materiais, diâmetros e incompletude.
- Exportação GeoJSON do conjunto filtrado. Inclui atributos preservados e `original_geometry`; a geometria principal está em WGS84.
- Opção PostGIS, índice GiST e consultas por extensão. SQLite usa índice RTree.
- Fonte ArcGIS autorizada pelo administrador, metadados, campos, consulta por IDs em lotes, rejeição de resposta incompleta e token só no backend.
- Limite de upload, validação de geometria e coordenadas, proteção de caminhos ZIP, senha de instância opcional e verificação de origem para operações de escrita.

## Importar sua rede real

1. Clique **Importar dados** e informe o nome de um novo projeto. Em um projeto real existente, deixe o nome vazio para acrescentar camadas ao mesmo projeto.
2. Escolha GeoJSON, ZIP ou GPKG. ZIP deve conter `.shp`, `.shx`, `.dbf` e preferencialmente `.prj`. `.cpg` é recomendado para codificação. Arquivos base com extensões minúsculas são a convenção suportada.
3. Se há várias camadas no ZIP/GPKG, informe o nome da camada. A mensagem de erro lista os nomes disponíveis.
4. Deixe o SRC vazio para usar metadados do arquivo. GeoJSON sem `crs` segue **RFC 7946 / EPSG:4326**. Se seu arquivo tiver coordenadas projetadas, informe o SRC correto; o sistema não assume 31982. Shapefile sem `.prj` exige seleção de SRC.
5. Clique **Ler arquivo e revisar campos**. Confira a amostra, o SRC e as sugestões.
6. Escolha a categoria correta da camada (PV, coletora etc.), nome e referência vertical. Campos ausentes podem ficar em **Não informado**.
7. **PV montante/inicial e PV jusante/final devem ser mapeados apenas quando forem confiáveis**, refletirem a direção da rede e corresponderem às extremidades inicial/final da geometria. Se os IDs forem somente cadastros sem direção ou a geometria estiver invertida, deixe sem mapear até corrigir/verificar a origem. O sentido da digitalização sozinho nunca estabelece fluxo.
8. Confirme a importação. O projeto real aparece no seletor superior e o mapa enquadra sua extensão.
9. Repita para PVs e outras camadas no mesmo projeto. Identificadores de PV e de extremidades devem usar exatamente a mesma convenção textual.

Limites locais: 30 MB por upload (ajustável em `MAX_UPLOAD_MB`), 200 MB após descompactação ZIP, 1000 membros por ZIP e 100.000 feições por importação. A validação é atômica: uma geometria inválida rejeita a camada inteira, sem descarte silencioso. As prévias expiram após uma hora na limpeza de novas importações e são limpas na reinicialização. Não execute várias instâncias compartilhando a pasta temporária.

## PostGIS opcional

O modo SQLite atende ao uso local leve. Para salvar em PostGIS, instale `requirements-gis.txt` e use um banco existente ou o Compose incluído. **Docker não é necessário para o restante da aplicação.**

Linux/macOS:

```bash
export POSTGRES_PASSWORD='uma-senha-local-forte'
docker compose up -d database
export DATABASE_URL='postgresql://cidade:uma-senha-local-forte@127.0.0.1:5432/cidade'
.venv/bin/python run.py
```

PowerShell:

```powershell
$env:POSTGRES_PASSWORD='uma-senha-local-forte'
docker compose up -d database
$env:DATABASE_URL='postgresql://cidade:uma-senha-local-forte@127.0.0.1:5432/cidade'
.venv\Scripts\python run.py
```

Aguarde o banco ficar saudável (`docker compose ps`) antes de iniciar. Para senhas com caracteres reservados, use codificação percentual na URL PostgreSQL. O app cria esquema e índices na partida. O volume `cidade_database` persiste os dados. `docker compose down` para o serviço; **não use `down -v` se quiser preservar o banco**.

SQLite e PostGIS são bases distintas: mudar `DATABASE_URL` não migra a base anterior. Não há sincronização ou migração automática. Exporte/reimporte se precisar transferir dados. Confira `database/README.md`.

## FeatureServer ArcGIS Enterprise

O navegador não aceita URLs arbitrárias. Um administrador deve configurar uma lista exata de fontes no ambiente do servidor. Exemplo PowerShell:

```powershell
$env:ARCGIS_SOURCES='{"rede":{"name":"Rede municipal","url":"https://gis.exemplo.gov.br/server/rest/services/Saneamento/FeatureServer/0","token_env":"ARCGIS_TOKEN"}}'
$env:ARCGIS_TOKEN='TOKEN_AUTORIZADO_OBTIDO_PELA_SUA_ORGANIZACAO'
.venv\Scripts\python run.py
```

Linux/macOS:

```bash
export ARCGIS_SOURCES='{"rede":{"name":"Rede municipal","url":"https://gis.exemplo.gov.br/server/rest/services/Saneamento/FeatureServer/0","token_env":"ARCGIS_TOKEN"}}'
export ARCGIS_TOKEN='TOKEN_AUTORIZADO_OBTIDO_PELA_SUA_ORGANIZACAO'
.venv/bin/python run.py
```

Para serviços públicos, omita `ARCGIS_TOKEN`. Use HTTPS e URL da **camada**, terminando em `/FeatureServer/0` (ou outro número). Permita somente serviços confiáveis; o cadastro no ambiente é a lista autorizada de destinos. Redirecionamentos não são seguidos. O administrador deve controlar DNS/egresso, especialmente para fontes internas autorizadas.

Abra Importar dados, selecione a fonte e clique **Ler FeatureServer**. Os mesmos passos de revisão e confirmação de campos são aplicados. O conector consulta IDs e busca lotes limitados por `maxRecordCount`. Falhas de autorização, limite ou resposta incompleta impedem o salvamento.

O serviço é consultado com `outSR=4326`: a geometria original preservada neste caso é a **resposta reprojetada pelo serviço**, não o arquivo de origem do ArcGIS. Os metadados originais do serviço, inclusive seu SRC, são guardados em `layers.source_metadata`. Para preservar coordenadas nativas exatamente como cadastradas, importe um arquivo exportado no SRC original.

Não há renovação automática de token, login OAuth/IWA nem suporte a polígonos ArcGIS neste conector; use credenciais autorizadas com prazo adequado ou exportação por arquivo. Não coloque token em URL, arquivos versionados ou formulário do navegador. Rede privada/VPN precisa ser acessível ao processo Python. Este ambiente não teve acesso a seu Enterprise real; o conector foi testado com respostas simuladas.

## Regras de análise e limitações

**A simulação é topológica, não hidráulica.** Não há previsão de vazão, pressão, extravasamento ou capacidade, nem motor SWMM integrado.

A topologia usa extremidades de LineString, não interseções no meio dos segmentos. IDs explícitos têm precedência. Nós com IDs não são fundidos automaticamente com nós sem IDs por proximidade. Geometrias com IDs iguais e posições divergentes são conectadas pelos IDs, mas geram ambiguidade para revisão. Sem IDs, uma projeção AEQD local em metros é construída para a área da rede. A tolerância (0–20 m, padrão 0,5 m) aparece no resultado. Extremos próximos de múltiplos candidatos ficam separados e são sinalizados. Para bases regionais muito extensas, divida em áreas adequadas antes da análise.

Um componente só é considerado dirigido se **todas** as suas arestas tiverem montante/jusante mapeados. Caso contrário, o conjunto é explorado sem afirmar sentido de fluxo. PVs usam IDs coincidentes ou correspondências geométricas com nós inferidos. LineString multipartes (`MultiLineString`) é desenhada e contabilizada, mas excluída da topologia com contagem explícita; converta em trechos simples verificáveis na origem. Nós de grau 1 são indícios, incluindo entradas e saídas legítimas, não defeitos confirmados.

A consulta retangular retorna comprimentos **integrais** dos trechos relacionados, não extensões recortadas. Em SQLite a consulta usa caixas envolventes; em PostGIS, interseção geométrica. Indicadores seguem filtros de pesquisa/material/diâmetro/tipo; visibilidade de camada e destaque são controles visuais e não alteram o escopo estatístico. As análises de topologia usam a **base completa**, com aviso no painel; somente o destaque renderizado respeita o filtro atual.

O **3D é ilustrativo nesta versão**, mesmo que existam Z/cotas no arquivo: dados verticais são preservados para consulta, mas ainda não há configuração validada de datum vertical/MDT para convertê-los em alturas elipsoidais do Cesium. A profundidade simbólica não é cota real. A superfície é o elipsoide WGS84. O carregamento 3D se limita a 5000 feições por vez, informado na tela, e desenha linhas/pontos, não cilindros em escala física, construções ou MDT real. Medição e consulta de área são feitas em 2D. O mapa-base OpenStreetMap pode ser ativado em 2D e 3D. Em 3D, ajuste a opacidade do globo para visualizar melhor ruas ou subsolo.

A aplicação entrega um fluxo local funcional, mas **não implementa integralmente todos os recursos avançados do documento original**. Pendências:

- Altimetria técnica/MDT, transformação de datum vertical e integração hidráulica validada.
- Tiles vetoriais, simplificação por escala, paginação automática por viewport, cache de grafos e processamento assíncrono de grandes importações. O endpoint `features?bbox=` já consulta os índices espaciais; o frontend atual carrega a base filtrada inteira.
- Ferramenta de corrigir/normalizar topologia, edições, exclusão de camadas, gerenciamento avançado de projetos e relatórios técnicos.
- Autenticação multiusuário, permissões por projeto, auditoria, migrações formais, filas e limitação de requisições para produção.
- Validação com sua rede real e seu ArcGIS Enterprise, que não foram fornecidos.

## Estrutura

```text
cidade-invisivel/
  run.py                      # inicialização única
  backend/
    main.py                   # API, segurança local, importação em duas fases
    geo.py                    # formatos, SRC, mapeamento e atributos
    store.py                  # SQLite/RTree e PostGIS/GiST
    topology.py               # conexões, percurso e interrupção
    arcgis.py                 # conector autorizado e paginação
    demo.py                   # rede sintética isolada
  frontend/
    index.html                # interface
    style.css                 # tema e layout responsivo
    app.js                    # mapas, controles, animação e painéis
    vendor/                   # criado por download_assets.py (bibliotecas e licenças)
  tests/test_system.py        # testes de integração e geoprocessamento
  scripts/download_assets.py  # recuperação opcional das bibliotecas
  scripts/check_postgis.py    # verificação com PostGIS descartável
  database/README.md
  docker-compose.yml          # somente banco opcional
  requirements*.txt
  .env.example
```

`run.py` lê variáveis de ambiente do processo; `.env.example` é documentação, não é carregado automaticamente pelo Python. O Compose lê `.env` para interpolação do banco. A documentação interativa da API está em `/docs` e não contém dados de rede; com senha configurada, chamadas à API exigem `Authorization: Bearer SUA_SENHA`.

## Testes

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Cobertura: prévia e persistência, atributos extras, formatos ZIP/GPKG, reprojeção 31982/4674, Z, conexões dirigidas/não dirigidas, PVs, cenários a montante, tolerância métrica, ambiguidades, filtros, extensão espacial, isolamento da demonstração, senha/origem e ZIP inseguro. ArcGIS é testado com mock de consulta por lotes e token de backend.

Para testar PostGIS, aponte `DATABASE_URL` para um **banco descartável** e execute:

```bash
python scripts/check_postgis.py
```

O script cria e remove seu próprio projeto de teste, confirma SRID, Z e índice GiST. Confira `VALIDACAO.md` para os resultados obtidos na entrega.

## Publicação segura

Por padrão, o processo escuta apenas `127.0.0.1`. Para acesso fora da máquina, `run.py` exige `APP_PASSWORD` quando `HOST` não é loopback. O diálogo ⚙ permite informar essa senha, mantida somente na memória da aba. A senha única de instância é apropriada para uso local controlado, **não substitui identidade e permissões de produção**.

Antes de publicar, implementar identidade/OIDC e autorização por projeto, TLS em proxy reverso, controle de origem/hosts, gestão de segredos, rate limits, limites de corpo no proxy e auditoria sem atributos sensíveis. Restringir rede do banco e egresso ArcGIS, criar usuário de banco com menor privilégio, aplicar migrações fora do processo da aplicação, realizar backups e testes de restauração, atualizar dependências e validar fontes/licenças e políticas da organização. Não publicar `data/`, tokens ou exportações. Todos os projetos da instância atualmente compartilham a mesma credencial. Não exponha esta versão diretamente à internet.

### Verificação opcional da interface

Para desenvolvedores: instale `requirements-browser.txt`, execute `python -m playwright install chromium` e depois `python scripts/check_browser.py`. Se já houver Chromium compatível, configure `BROWSER_EXECUTABLE` com seu caminho e dispense o download do navegador. O script inicia um servidor temporário em `127.0.0.1:8001`, usa um banco descartável, testa o formulário de importação e o clique real na rede e salva capturas em `work/browser-checks/`. A porta deve estar livre e `APP_PASSWORD`/`DATABASE_URL` devem estar desconfiguradas para esse teste isolado. Esse teste é opcional e não faz parte da instalação para uso do aplicativo.

## Ativar OpenStreetMap (2D e 3D)

Clique **Mapa-base: desligado** na barra sobre o mapa. O botão passa a **Mapa-base: OSM (2D)** ou **OSM (3D)**. A opção acompanha a alternância entre os modos. Em 3D, use a opacidade do globo para equilibrar a visualização das ruas e da rede subterrânea. A ativação é feita por aba e não exige token ou instalação adicional.

É necessário acesso do **navegador** a `https://tile.openstreetmap.org`. Se as ruas não aparecerem:

1. Confirme que atualizou `backend/main.py` e `frontend/app.js`; reinicie `python run.py` e atualize a página com **Ctrl+F5**. Não substitua sua pasta `data/`.
2. Abra https://tile.openstreetmap.org/0/0/0.png no navegador para verificar conectividade com o servidor de tiles. Isso verifica acesso ao domínio, mas não substitui a verificação de cabeçalhos/CORS das requisições do mapa.
3. Se houver bloqueio de rede, antivírus ou extensão, verifique a liberação desse domínio com o administrador. O console do navegador (F12 → Rede) permite identificar 403, 429 ou falhas de conexão.
4. Se usar proxy reverso, não sobrescreva `Referrer-Policy` com `no-referrer` ou `same-origin`: OSM requer Referer válido para pedidos web. A interface agora usa `strict-origin-when-cross-origin`, enviando somente a origem para destinos externos. A API mantém `no-referrer`. Não desabilite CORS ou a verificação de certificados para tentar corrigir conectividade.

Os tiles são pedidos diretamente ao OSM, com atribuição, cache normal do navegador e sem pré-carregamento em massa. A disponibilidade depende do serviço e da rede do usuário. Esta mudança não inclui um servidor offline de mapas ou download de cidades inteiras. O mapa-base continua desligado na abertura para evitar consultas externas antes da ativação explícita.

Teste opcional e reproduzível desta integração: com `requirements-browser.txt` e Chromium instalados, execute `python scripts/check_basemap.py`. Ele usa tiles PNG sintéticos interceptados no navegador, sem acessar o OSM real, e verifica Referer, atribuição, ativação/desativação em 2D/3D e tratamento de HTTP 403. A porta 8003 deve estar livre.
