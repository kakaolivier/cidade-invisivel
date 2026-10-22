# Validação da entrega — 20/10/2026

## Ambiente

Python 3.12, Linux x86_64, Chromium headless com WebGL/SwiftShader. Nenhuma ferramenta Node foi usada para instalar, compilar ou executar o projeto. Dependências e bibliotecas de mapa têm versões fixas nos arquivos de instalação e no script de download.

## Resultados

- **14 testes automatizados passaram**, em 1,06 s: `python -m pytest -q`.
- Importação GeoJSON, Shapefile ZIP e GeoPackage verificada com arquivos gerados durante os testes.
- Reprojeção EPSG:31982 e EPSG:4674 para WGS84 verificada numericamente.
- Preservação de atributos extras, geometria de origem e coordenadas Z verificada.
- Conectividade dirigida/não dirigida, associação de PVs, ramificações, interrupção a montante, tolerância em metros e ambiguidades verificadas.
- Pesquisa/filtros, consulta espacial vazia, isolamento demo/real, senha, origem de escrita e proteção contra caminhos ZIP verificadas.
- Conector ArcGIS testado com mock: metadados, lotes por IDs, token apenas no backend e persistência dos metadados do SRC original.
- **PostGIS 17 / extensão 3.5**, em contêiner temporário: escrita/leitura, consulta por extensão, preservação de atributos, SRID 4326, dimensão Z e presença do índice GiST passaram. O banco temporário foi encerrado/removido depois do teste.
- **Teste completo no navegador passou**: mapa 2D, clique real em tubulação, consulta de atributos, partícula animada, interrupção a montante, troca para Cesium 3D (13 entidades), formulário real de importação GeoJSON, confirmação de mapeamento, persistência após recarregar, filtro de diâmetro e retorno à demonstração sem mistura dos dados.
- **Zero erros JavaScript e zero requisições externas** no fluxo básico de demonstração e importação local. Bibliotecas e recursos do Cesium foram servidos localmente.
- Código Python compilado com `compileall` sem erro. Frontend sem etapa de build; JavaScript validado pela execução no Chromium.

O teste de clique real identificou que o renderizador MapLibre não conservava os UUIDs no campo de ID da feição retornada. A seleção foi corrigida para transportar o identificador em um atributo explícito e o teste passou após a correção.

Houve um aviso de depreciação de Starlette sobre seu adaptador TestClient com httpx, sem falha de teste. Ele se refere à ferramenta de testes; o conector ArcGIS usa httpx diretamente.

## Limites da validação

Não houve acesso à rede real do usuário, ao ArcGIS Enterprise privado, a MDT ou a referência vertical validada. Não foram feitos ensaios de carga para dezenas de milhares de segmentos nem auditoria de segurança para produção. O 3D validado é explicitamente ilustrativo. A simulação é topológica, não hidráulica. A versão não cobre integralmente os recursos avançados do documento original; veja as pendências no README.

A verificação visual foi realizada em desktop (1512 × 982). Há regras de adaptação para telas menores, mas tablets e navegadores móveis não foram validados em dispositivos reais.

## Atualização do mapa-base OpenStreetMap

- Corrigido Referrer-Policy da interface para strict-origin-when-cross-origin; a API mantém no-referrer.
- OSM habilitado no botão de mapa-base em 2D e 3D, com atribuição e opacidade 2D de 0,85.
- Acrescentada mensagem específica para falhas de tiles, sem interromper a rede carregada.
- Os 14 testes da API passaram novamente (1,07 s).
- scripts/check_basemap.py passou em Chromium: ativação explícita, tiles em 2D, Referer apenas com a origem, atribuição visível, provedor Cesium 3D, alternância e desativação, e aviso de HTTP 403. Zero erros JavaScript. Os tiles foram simulados (41 requisições interceptadas); não foi validada disponibilidade do serviço OSM na rede do usuário.

## Correção do escopo das ambiguidades

A consulta de percurso agora retorna alertas do componente conectado analisado em `ambiguities` e o total de alertas do projeto em `global_ambiguity_count`. A interface diferencia os dois contadores. Alertas de conexões recusadas são incluídos para os componentes dos nós candidatos, além do trecho que originou o alerta. O relatório geral de topologia continua considerando a base inteira.

16 testes automatizados passaram (1,28 s), incluindo dois testes de regressão com geometrias sintéticas para ambiguidades em componentes distintos. Nenhum arquivo geográfico do usuário integra o código ou os testes publicados.

## Percurso contínuo e bases extensas

- Nova API de percurso entre elementos, com destino explícito ou automático, menor extensão no grafo e limite de 500 trechos. Campos de início/fim geométrico são separados de direção declarada.
- O componente inteiro permanece disponível na ferramenta Destacar conexões; a animação usa uma sequência contínua de trechos.
- Pesquisa de PVs, enquadramento automático, progresso visível, velocidade de apresentação, parar/reiniciar e continuidade entre 2D/3D.
- Índice de feições no navegador, destaque incremental, geometrias de contexto limitadas ao enquadramento e prioridade da rota no 3D. Atributos originais são carregados sob demanda.
- Cache de topologia limitado a um projeto/tolerância, invalidado por novas camadas; consultas leves em SQLite e PostGIS.
- Limites de upload, ZIP e quantidade de feições agora configuráveis no ambiente. GeoPackages ignoram tabelas não geográficas na escolha automática de camada.
- **22 testes automatizados passaram** (1,24 s), incluindo rotas dirigidas/não dirigidas, orientação dos segmentos, destinos desconectados, importações antigas com códigos geométricos, preservação dos atributos, cache e registros paralelos.
- O teste de navegador confirmou movimento da partícula, seleção, importação, percurso, cenário e 3D com dados sintéticos, sem erros JavaScript ou requisições externas.
- PostGIS temporário: consultas leves, pesquisa, detalhe e percurso dirigido passaram.
- A animação também foi verificada em ambiente privado com os dados fornecidos na conversa, com seleção de destino, movimento em 2D/3D e parar/reiniciar. Os dados geográficos, imagens e resultados detalhados desse teste privado não integram o repositório.
