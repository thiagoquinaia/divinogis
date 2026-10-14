# 🧭 DivinoGIS — Registro Completo de Arquitetura, Funcionalidades e Contexto do Projeto

> **Finalidade deste documento**: Servir como guia definitivo e memória técnica permanente do projeto **DivinoGIS**. Todas as interações e desenvolvimentos futuros devem consultar este arquivo para preservar a integridade do código, evitar retrabalho e otimizar o consumo de tokens.

---

## 📌 1. Visão Geral do Sistema

- **Nome Oficial**: **DivinoGIS**
- **Repositório GitHub**: `https://github.com/thiagoquinaia/divinogis` (Público, branch `main`)
- **Proposta**: Sistema Web SIG Desktop completo, com layout e usabilidade inspirados no **QGIS Desktop 3.34 'Prizren'**, operando localmente via navegador (`http://localhost:5001`) ou via container Docker.
- **Porta padrão**: `5001` (para evitar conflito com AirPlay/Control Center do macOS na porta 5000).

---

## 🏗️ 2. Arquitetura e Estrutura de Arquivos

```
gerador_topo3d/ (divinogis)
├── app.py                      # Servidor Flask principal e roteamento da API REST
├── srtm_service.py             # Módulo de download, mosaico, hillshade e recorte de dados SRTM 30m
├── stl_service.py              # Gerador de malha 3D sólida manifold watertight para impressão 3D
├── ibge_service.py             # Integração com API v3 do IBGE, reprojeção e exportação GPKG/KML
├── run.sh                      # Shell script executável para inicialização rápida
├── requirements.txt            # Dependências Python rastreadas e versionadas
├── Dockerfile                  # Imagem Docker multi-stage com GDAL/GeoPandas
├── docker-compose.yml          # Subida automatizada de container com volumes persistentes
├── .dockerignore               # Exclusões para build de container
├── .gitignore                  # Regras de exclusão para Git (ignora caches pesados e exports)
├── LICENSE                     # Licença MIT aberta
├── README.md                   # Documentação pública completa para o GitHub
├── CONTRIBUTING.md             # Guia de contribuição para a comunidade open-source
├── CODE_OF_CONDUCT.md          # Código de conduta internacional Contributor Covenant 2.1
├── SECURITY.md                 # Política de segurança e reporte responsável de falhas
├── PROJECT_CONTEXT.md          # Este arquivo (memória técnica permanente do projeto)
├── .github/
│   ├── workflows/
│   │   └── ci.yml              # Pipeline GitHub Actions (validação de Python, JS e imports)
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md       # Template oficial para reporte de bugs
│   │   └── feature_request.md  # Template oficial para sugestão de novas funcionalidades
│   └── PULL_REQUEST_TEMPLATE.md# Checklist padronizado para Pull Requests
├── templates/
│   └── index.html              # Interface visual completa estilo QGIS Desktop (DOM e Modais)
├── static/
│   ├── css/
│   │   └── qgis-theme.css      # Folha de estilos fiel ao QGIS 3 (paleta, toolbars, diálogos, tabelas)
│   └── js/
│       └── app.js              # Lógica cliente (Leaflet, Three.js, IBGE, Tabela, Janelas arrastáveis)
├── data_cache/                 # Diretório de cache local (tiles HGT e GeoJSONs do IBGE)
│   ├── .gitkeep
│   ├── hgt/                    # Arquivos .hgt.gz baixados da AWS Open Data
│   └── ibge/                   # Malhas e listas de municípios/mesorregiões em cache local
└── exports/                    # Diretório de saída para arquivos gerados pelo usuário
    └── .gitkeep
```

---

## 🧩 3. Módulos e Funcionalidades Detalhadas

### 3.1. Relevo Topográfico NASA SRTM 30m (`srtm_service.py`)
- **Fonte**: NASA SRTM 1-ArcSecond (~30 metros de resolução espacial), servido via AWS Open Data / Skadi em tiles de 1°x1° (`.hgt.gz`).
- **Fluxo de Processamento**:
  1. O usuário delimita uma **Área de Interesse (AOI)** pelo mapa com a ferramenta de desenho retangular.
  2. O backend calcula os tiles necessários, baixa apenas os que faltam e salva no cache (`data_cache/hgt/`).
  3. Descompacta em memória (`gzip`) e cria uma matriz NumPy combinada (*mosaic*).
  4. Realiza o recorte (*crop*) georreferenciado exato da AOI.
  5. Aplica sombreamento de relevo analítico (*hillshade*) com azimute e ângulo de iluminação configuráveis via Matplotlib / NumPy.
  6. Gera e salva o arquivo **GeoTIFF georreferenciado (`.tif`)** com projeção `EPSG:4326 (WGS 84)` em `exports/`.
  7. Retorna metadados completos (cota mínima, média, máxima, dimensões em pixels e resolução).
- **Inspeção Altimétrica**: Endpoint `/api/elevation` permite clicar em qualquer ponto do mapa e ler a cota exata em metros a partir da matriz raster.

### 3.2. Modelagem STL Sólida para Impressão 3D (`stl_service.py`)
- **Objetivo**: Transformar o GeoTIFF de elevação em um arquivo **`.stl` sólido, fechado (watertight) e manifold**, pronto para fatiadores como Cura, PrusaSlicer e Bambu Studio.
- **Parametrizações**:
  - **Escala Cartográfica**: Pré-definições (1:10k, 1:25k, 1:50k, 1:100k, 1:250k) ou escala livre, com atalhos para adequar a mesas de 100 mm, 150 mm, 200 mm ou 250 mm.
  - **Exagero Vertical**: Multiplicador de 1.0x a 5.0x (ou mais) com cálculo instantâneo da cota Z em milímetros.
  - **Espessura da Base**: Base sólida plana (padrão 2.5 mm) para garantir adesão perfeita na mesa da impressora.
  - **Suavização Gaussiana**: Filtro `scipy.ndimage.gaussian_filter` ajustável (0.0 a 3.0) para remover o efeito de escada (*stepping*) nativo de dados discretos de satélite.
  - **Cálculo em Tempo Real no Cliente**: A interface recalcula instantaneamente no navegador:
    $$\text{Largura (X mm)} = \frac{\text{Distância Real X (m)} \times 1000}{\text{Denominador da Escala}}$$
    $$\text{Comprimento (Y mm)} = \frac{\text{Distância Real Y (m)} \times 1000}{\text{Denominador da Escala}}$$
    $$\text{Relevo Z (mm)} = \left(\frac{\Delta Z \text{ Real (m)} \times 1000}{\text{Denominador da Escala}}\right) \times \text{Exagero Vertical}$$
    $$\text{Altura Total Z (mm)} = \text{Base Sólida (mm)} + \text{Relevo Z (mm)}$$
- **Geração da Geometria STL**:
  - Superfície superior: grelha de triângulos calculada a partir do raster suavizado.
  - Fundo plano: vértices invertidos na cota zero.
  - Quatro paredes laterais verticais: triangulação de fechamento que une as bordas do relevo à base plana.
  - Normais de triângulos calculadas via produto vetorial e exportação em formato STL binário de alta performance.

### 3.3. Visualizador 3D Interativo (Three.js WebGL)
- Modal com canvas Three.js e `OrbitControls`.
- Cria uma `PlaneGeometry` correspondente às dimensões reais do raster.
- Deforma os vértices com base nos valores altimétricos normalizados multiplicados pelo exagero vertical.
- Mapeia a textura hipsométrica com sombreamento gerada pelo servidor.
- Controles na barra inferior da janela 3D:
  - Slider de exagero vertical interativo.
  - Checkbox para alternar entre textura sólida e malha de triângulos (*wireframe*).
  - Botão para resetar câmera.

### 3.4. Malhas Cartográficas Oficiais do IBGE (`ibge_service.py`)
- **Integração**: Conecta-se diretamente aos endpoints oficiais da API v3 de Malhas do IBGE:
  - `brasil`: Contorno territorial da República Federativa do Brasil.
  - `regioes`: As 5 Grandes Regiões (Norte, Nordeste, Centro-Oeste, Sudeste, Sul).
  - `estados`: As 27 Unidades da Federação.
  - `mesorregioes_brasil`: As 137 Mesorregiões geográficas de todo o país.
  - `mesorregioes`: Mesorregiões filtradas por UF (ex: 15 mesorregiões de SP, 12 de MG).
  - `municipios`: Todos os municípios da UF selecionada (ex: 645 municípios em SP, 853 em MG).
- **Cache Inteligente**: GeoJSONs baixados são salvos em `data_cache/ibge/`, garantindo carregamento instantâneo nas próximas consultas.
- **Enriquecimento de Metadados**: A API de malhas puras retorna apenas `codarea`. O serviço `ibge_service.py` cruza com a API de localidades do IBGE e adiciona:
  - `CD_UF`, `NM_UF`, `SIGLA_UF`, `NM_REGIAO`, `CD_MESO`, `NM_MESO`, `CD_MUN`, `NM_MUN`.
  - `AREA_KM2`: cálculo geodésico de área em quilômetros quadrados via Shapely.

### 3.5. Exportador Vetorial com Reprojeção de SRC
- **Menu de Contexto (Botão Direito)** sobre a camada vetorial ➔ **"Exportar Camada Vetorial (.gpkg, .kml)..."**.
- **Janela Popup Dedicada**:
  - Seleção de Formato:
    - **GeoPackage (`.gpkg`)**: Padrão moderno OGC / SQLite aberto com indexação espacial e tabela de atributos.
    - **Keyhole Markup Language (`.kml`)**: Gerador customizado OGC KML 2.2 com `<ExtendedData>` para preservar os atributos no Google Earth e QGIS.
    - **GeoJSON (`.geojson`)** e **ESRI Shapefile (`.zip`)**.
  - Seleção de Sistema de Referência de Coordenadas (SRC / CRS):
    - `EPSG:4674` — **SIRGAS 2000** (Oficial Brasil / IBGE)
    - `EPSG:4326` — **WGS 84** (Geográfico GPS)
    - `EPSG:3857` — **WGS 84 / Pseudo-Mercator** (Web Mercator)
    - `EPSG:31983` — **SIRGAS 2000 / UTM zone 23S** (Sudeste/SP/MG)
    - `EPSG:31982` — **SIRGAS 2000 / UTM zone 22S** (Sul/PR/SC/RS)
    - `EPSG:31984` — **SIRGAS 2000 / UTM zone 24S** (Nordeste/BA)
  - Campo editável para nome do arquivo.
- **Motor de Reprojeção**: GeoPandas + PyProj reprojetam as geometrias no servidor antes da gravação do arquivo e disparam o download imediato.
- **Proteção Antiestrutura Circular**: O cliente extrai apenas cópias limpas e estritas das features `{ type, geometry, properties }`, eliminando qualquer referência circular do Leaflet (`fLayer.feature`).

### 3.6. Visualizador da Tabela de Atributos (Estilo QGIS)
- **Acesso**: Botão direito na camada vetorial ➔ **"Abrir Tabela de Atributos..."** ou botão na barra de ferramentas.
- **Recursos**:
  - Grid estilo planilha desktop com cabeçalho fixo (*sticky header*) e numeração de linhas (`#`).
  - Campo de busca instantâneo que filtra linhas em tempo real à medida que o usuário digita.
  - **Interação Bi-direcional com o Mapa**:
    - Ao clicar em uma linha da tabela, a linha fica azul selecionada.
    - O mapa centraliza e aproxima (*zoom com padding*) na geometria correspondente.
    - O polígono no mapa recebe realce em amarelo/laranja vivo (`weight: 3.5, color: #ff9800, fillColor: #ffeb3b`).
    - O popup cadastral com todos os atributos da feição é aberto na tela.
  - **Exportação CSV**: Botão para exportar os dados (filtrados ou completos) com codificação UTF-8 BOM (`\uFEFF`), abrindo perfeitamente com acentuação correta no Microsoft Excel e LibreOffice.

### 3.7. Recorte Automático de SRTM 30m por Feição Vetorial Selecionada (Polygon Cutline)
- **Objetivo**: Permitir que o usuário selecione qualquer polígono vetorial ativo (ex: município do IBGE, mesorregião, contorno estadual ou feição customizada) e baixe o raster SRTM 30m já recortado estritamente pela geometria do polígono, com transparência total nas bordas externas.
- **Pontos de Acionamento na Interface**:
  1. **Popup no Mapa**: Ao clicar em qualquer município ou polígono no mapa, o popup exibe os atributos e um botão direto destacado: `[⛰️ Extrair e Recortar SRTM 30m]`.
  2. **Barra de Ferramentas Principal**: Botão dedicado `[⛰️ SRTM da Feição]` ao lado de "Solicitar SRTM (AOI)".
  3. **Tabela de Atributos**: Botão `[⛰️ Extrair SRTM]` na barra superior da tabela, operando sobre a linha selecionada.
  4. **Menu de Contexto**: Opção `[⛰️ Extrair SRTM 30m da Feição Selecionada]` ao clicar com botão direito na camada vetorial.
- **Motor de Recorte no Servidor (`srtm_service.py`)**:
  - Aceita `geometry` (GeoJSON Polygon ou MultiPolygon), `feature_name` e `resolution` ('auto', '30m', '60m', '90m').
  - Extrai `bounds` automáticos da feição via Shapely.
  - **Download Paralelo Concorrente (`ThreadPoolExecutor`)**: Baixa as quadrículas HGT em paralelo com até 10 threads, acelerando o download de áreas extensas em até 8x.
  - **Resolução Adaptativa Inteligente (Suporte a Grandes Áreas)**:
    - Áreas de até **8.0° x 8.0°** (ex: Triângulo Mineiro de 90.721 km², 5.43° x 2.52°, e 100% das mesorregiões e estados médios): processamento a **30m nativo (SRTM 1-arcsec)** com total fidelidade topográfica.
    - Áreas de **8.0° a 14.0°** (grandes estados como Bahia e Minas Gerais): resolução adaptada automaticamente para 60m (2-arcsec).
    - Áreas de **14.0° a 22.0°**: resolução adaptada para 90m (3-arcsec).
  - **Geração Otimizada de Visualização PNG**: Imagens de pré-visualização para o Leaflet são sub-amostradas para caber em 2400 pixels, garantindo geração em menos de 1 segundo e evitando estouro de memória no navegador e no Pillow.
  - Aplica máscara poligonal booleana com `rasterio.features.geometry_mask(invert=True)`.
  - Células externas à feição recebem o valor NoData (`-32768`).
  - Geração de imagem PNG com canal alfa transparente (`rgba[~valid_mask, 3] = 0`) para sobreposição perfeita no mapa Leaflet.
  - Totalmente compatível com download de GeoTIFF recortado, visualizador 3D Three.js e exportação STL para impressão 3D.

### 3.8. Sistema de Janelas Flutuantes Arrastáveis (Draggable Popups)
- Todas as janelas de diálogo (`.qgis-dialog` dentro de `.qgis-modal-backdrop`) são **arrastáveis** segurando pela barra de título cinza superior (`.dialog-titlebar`).
- Cursor dinâmico `grab` / `grabbing`.
- Fundo semitransparente suave com `pointer-events: none` na cortina e `pointer-events: auto` no diálogo, permitindo que o usuário arraste as janelas para a lateral e continue interagindo livremente com o mapa (pan e zoom).
- Limites automáticos para não deixar as janelas saírem da área visível da tela.

---

## 🌐 4. Rotas da API REST (`app.py`)

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/` | Renderiza a página principal do DivinoGIS (`templates/index.html`) |
| `POST` | `/api/srtm` | Processa AOI, baixa tiles HGT, gera mosaico, recorte e salva GeoTIFF |
| `GET` | `/api/elevation` | Consulta cota altimétrica pontual por `lat`, `lon` e `layer_id` |
| `GET` | `/api/search` | Consulta localidades via Nominatim OpenStreetMap |
| `POST` | `/api/export-stl` | Gera modelo STL sólido manifold com escala, base, suavização e exagero |
| `GET` | `/api/ibge/ufs` | Retorna lista ordenada das 27 UFs com códigos, siglas e regiões |
| `GET` | `/api/ibge/mesh` | Retorna malha vetorial GeoJSON oficial (Brasil, Regiões, UFs, Mesos, Munics) |
| `POST` | `/api/ibge/export` | Reprojeta SRC e exporta vetor para `.gpkg`, `.kml`, `.geojson` ou `.zip` (SHP) |
| `GET` | `/api/download/<filename>` | Download de arquivos raster/STL gerados em `exports/` |
| `GET` | `/api/download-vector/<filename>` | Download de arquivos vetoriais gerados em `exports/` |
| `DELETE` | `/api/layers/<layer_id>` | Remove arquivos temporários de uma camada raster excluída |

---

## 💡 5. Decisões Técnicas e Lições Aprendidas

1. **Evitar Referências Circulares no Leaflet**:
   - Nunca atribuir o objeto Leaflet `fLayer` diretamente dentro do objeto GeoJSON `feature` (ex: `feature._leafletLayer = fLayer`), pois o Leaflet já guarda `fLayer.feature = feature`, criando um ciclo que quebra o `JSON.stringify`.
   - Manter um array separado `reg.featureLayers[idx] = fLayer`.
2. **Compatibilidade KML e Fiona/GDAL**:
   - A biblioteca Fiona padrão do Python frequentemente não é compilada com suporte de escrita ao driver KML do GDAL.
   - Solução adotada: implementamos o gerador direto OGC KML XML em `ibge_service.py` (`convert_geojson_to_kml`), que gera arquivos KML 2.2 limpos, com suporte a Polygon, MultiPolygon e `<ExtendedData>` para atributos, sem depender de drivers externos.
3. **GeoPackage (.gpkg)**:
   - A escrita via GeoPandas (`gdf.to_file(..., driver='GPKG')`) requer a remoção prévia de arquivo pré-existente com o mesmo nome para evitar bloqueios de lock do SQLite.
4. **Porta do Servidor**:
   - Manter sempre a porta `5001` (ou variável de ambiente `PORT`), pois no macOS a porta 5000 é usada pelo serviço nativo AirPlay Receiver.
5. **Estrutura Git e Arquivos Pesados**:
   - As pastas `data_cache/` e `exports/` contêm apenas arquivos `.gitkeep` versionados. Todos os `.tif`, `.hgt.gz`, `.stl`, `.gpkg` e `.geojson` gerados em tempo de execução são ignorados pelo `.gitignore`.

---

## 🎯 6. Guia de Trabalho para Interações Futuras

Ao retomar ou continuar o desenvolvimento do DivinoGIS:
- **Consulte este arquivo primeiro** para verificar como as funções e rotas existentes se comunicam.
- **Mantenha a estética QGIS 3**: botões pequenos e compactos, paleta clássica cinza/azul/verde, toolbars modulares e bordas sutis.
- **Preserve o suporte a janelas arrastáveis**: se um novo modal for criado, utilize a classe `.qgis-modal-backdrop` e `.qgis-dialog` com `.dialog-titlebar`.
- **Commits e Branches**: A branch padrão oficial do repositório é `main`.

---
*Documento gerado em 14 de Outubro de 2026 para o projeto DivinoGIS.*
