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
