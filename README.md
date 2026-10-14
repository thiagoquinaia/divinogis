# 🌐 DivinoGIS - Web Desktop SIG

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/Flask-3.0-green?logo=flask" alt="Flask" />
  <img src="https://img.shields.io/badge/GDAL%2FRasterio-Geospatial-success" alt="Rasterio" />
  <img src="https://img.shields.io/badge/GeoPandas-Vector-brightgreen" alt="GeoPandas" />
  <img src="https://img.shields.io/badge/Leaflet-1.9-yellow?logo=leaflet" alt="Leaflet" />
  <img src="https://img.shields.io/badge/Three.js-3D%20WebGL-black?logo=three.js" alt="Three.js" />
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License" />
</p>

**DivinoGIS** é uma plataforma web SIG com experiência visual e funcional inspirada no **QGIS Desktop 3**. Projetada para engenheiros, geógrafos, modelistas 3D e pesquisadores, ela permite:

1. Delimitar interativamente Áreas de Interesse (AOI) e extrair dados originais de elevação **NASA SRTM 1-arcsecond (~30m)** com exportação imediata em **GeoTIFF (`.tiff`)**.
2. Transformar o relevo topográfico em sólidos **STL (`.stl`) manifold watertight** prontos para **impressão 3D e CAD**, com controle em tempo real de dimensões em milímetros, escalas métricas, espessura da base, suavização gaussiana e exagero vertical.
3. Carregar malhas vetoriais oficiais do **IBGE** (Brasil, Grandes Regiões, Estados, Mesorregiões e Municípios) diretamente no mapa e na árvore de camadas.
4. Exportar camadas vetoriais em **GeoPackage (`.gpkg`)** e **KML (`.kml`)** através de um popup dedicado com seleção de **SRC/CRS** (SIRGAS 2000, WGS 84, UTM) e reprojeção geodésica em tempo real.
5. Inspecionar feições através de um **Visualizador da Tabela de Atributos** estilo planilha QGIS com busca dinâmica, exportação CSV e interação bi-direcional com o mapa (ao clicar na feição, o mapa aproxima e realça o polígono).
6. **Janelas Modais Arrastáveis**: todas as janelas do sistema podem ser movidas livremente pela tela segurando pela barra de título.

---

## ⚡ Recursos Principais

### 1. 🗺️ Interface Desktop e Painel de Camadas
- Barra de menus clássica (`Projeto`, `Editar`, `Exibir`, `Camada`, `Raster`, `IBGE`, `Ajuda`).
- Barra de status com exibição de coordenadas geográficas (`Lat/Lon`), escala dinâmica e código EPSG ativo.
- Painel de Camadas (dock esquerdo) com ordenação, controle de visibilidade via checkbox, opacidade ajustável e legendas com rampa de cores e cotas altimétricas (Min, Méd, Max).
- Menu de contexto (botão direito) especializado com ferramentas distintas para dados Raster e Vetoriais.

### 2. ⛰️ Extração NASA SRTM 30m Global
- Ferramenta **Definir AOI**: desenhe retângulos diretamente no mapa para obter a área exata em km².
- Conexão em nuvem com repositório global AWS Open Data / Skadi (HGT 1°x1°).
- Fusão automática de tiles, recorte georreferenciado e geração instantânea de imagem sombreada (*hillshade*) e arquivo **GeoTIFF padrão OGC**.
- Ferramenta **Identificar**: clique em qualquer ponto do mapa para inspecionar a cota altimétrica em metros.

### 3. 🖨️ Modelagem e Exportação STL para Impressão 3D
- **Cálculo de Dimensões em Tempo Real**: veja a **Largura (X em mm)**, **Comprimento (Y em mm)**, **Desnível do Relevo**, **Base Sólida** e **Altura Total (Z em mm)** a cada clique.
- **Escalas Pré-definidas**: 1:10.000, 1:25.000, 1:50.000, 1:100.000, 1:250.000 ou escala personalizada.
- **Ajuste Rápido para Mesa 3D**: botões de 1 clique para adequar a peça a mesas de 100 mm, 150 mm, 200 mm ou 250 mm.
- **Exagero Vertical**: multiplicador de elevação (1x, 1.5x, 2x, 3x, 4x, 5x) com readequação imediata da altura do objeto.
- **Filtro de Suavização Gaussiana**: atenua ruídos e elimina o efeito de degraus (*stepping*), produzindo curvas suaves e contínuas.
- **Sólido Manifold Watertight**: modelo 3D fechado com 4 paredes verticais e fundo perfeitamente plano, compatível com Cura, PrusaSlicer, Bambu Studio e Blender.

### 4. 🌐 Visualizador 3D do Relevo (WebGL / Three.js)
- Navegação em órbita com controles de rotação, aproximação (zoom) e deslocamento (pan).
- Modos com textura de relevo hipsométrico sombreado ou malha aramada (*wireframe*).
- Controle dinâmico de exagero vertical no ambiente tridimensional.

### 5. 🏛️ Malhas Vetoriais Oficiais do IBGE
- Acesso direto à API de Malhas Geográficas do IBGE:
  - 🇧🇷 **Contorno do Brasil** (Limite nacional)
  - 🗺️ **Grandes Regiões** (5 macrorregiões)
  - 🏛️ **Estados / UFs** (As 27 Unidades da Federação)
  - 🌐 **Mesorregiões do Brasil** (137 mesorregiões completas)
  - 📍 **Mesorregiões por Estado** (Filtradas por UF selecionada)
  - 🏙️ **Municípios por Estado** (Todos os municípios com nomes e códigos oficiais)
- Metadados completos integrados com a API de localidades do IBGE e cálculo automático de área geodésica em km².

### 6. 📦 Exportação Vetorial com Reprojeção de SRC
- Janela popup dedicada para exportar qualquer camada vetorial.
- **Formatos suportados**:
  - `GeoPackage (.gpkg)`: Padrão moderno OGC / SQLite aberto.
  - `Keyhole Markup Language (.kml)`: OGC KML com tabela de atributos `<ExtendedData>` para Google Earth e web.
  - `GeoJSON (.geojson)`: Formato aberto padrão IETF.
  - `ESRI Shapefile (.zip)`: Compactado com arquivos `.shp`, `.shx`, `.dbf` e `.prj`.
- **Sistemas de Coordenadas de Referência (SRC / CRS)**:
  - `EPSG:4674` — SIRGAS 2000 (Padrão Oficial Brasil / IBGE)
  - `EPSG:4326` — WGS 84 (Geográfico GPS)
  - `EPSG:3857` — WGS 84 / Pseudo-Mercator (Web Mercator)
  - `EPSG:31983` — SIRGAS 2000 / UTM zone 23S (Sudeste/SP/MG)
  - `EPSG:31982` — SIRGAS 2000 / UTM zone 22S (Sul/PR/SC/RS)
  - `EPSG:31984` — SIRGAS 2000 / UTM zone 24S (Nordeste/BA)

### 7. 📊 Tabela de Atributos Interativa
- Visualizador estilo planilha desktop com cabeçalho fixo e numeração de linhas.
- Campo de busca instantâneo para filtrar feições em tempo real.
- **Link com o Mapa**: ao clicar em uma linha da tabela, o mapa aproxima com zoom dinâmico e destaca o polígono em amarelo/laranja vivo, exibindo sua ficha cadastral.
- Botão para exportação em arquivo CSV com codificação UTF-8 BOM (compatível diretamente com Microsoft Excel e LibreOffice Calc).

---

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python 3.10+, Flask, Rasterio (GDAL), GeoPandas, Shapely, PyProj, SciPy, NumPy, Matplotlib, Pillow, Requests.
- **Frontend**: Vanilla JavaScript (ES6+), Leaflet.js, Leaflet-Draw, Three.js, OrbitControls.
- **Estilos**: CSS3 temático inspirado no layout do QGIS Desktop.
- **Fontes de Dados**: NASA SRTM v3.0 (AWS Open Data), IBGE API v1/v3, OpenStreetMap, OpenTopoMap, Esri World Imagery, CartoDB Positron.

---

## 🚀 Como Executar o Projeto

### Opção 1: Execução Local (Linux / macOS / Windows)

#### 1. Clone o repositório
```bash
git clone https://github.com/thiagoquinaia/divinogis.git
cd divinogis
```

#### 2. Crie e ative um ambiente virtual
```bash
python3 -m venv venv

# No Linux ou macOS:
source venv/bin/activate

# No Windows (PowerShell):
.\venv\Scripts\Activate.ps1
```

#### 3. Instale as dependências
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Inicie o servidor
```bash
# Via script:
./run.sh

# Ou diretamente pelo Python:
python3 app.py
```

Acesse no navegador:
👉 **[http://localhost:5001](http://localhost:5001)**

---

### Opção 2: Execução via Docker / Docker Compose

Se preferir não instalar dependências geospaciais no seu sistema:

```bash
docker compose up --build
```

Acesse no navegador:
👉 **[http://localhost:5001](http://localhost:5001)**

---

## 📂 Estrutura do Projeto

```
divinogis/
├── app.py                  # Servidor Flask principal e roteamento da API REST
├── srtm_service.py         # Módulo de download, mosaico e recorte de dados SRTM 30m
├── stl_service.py          # Gerador de malha 3D sólida STL manifold para impressão
├── ibge_service.py         # Integração com API do IBGE, reprojeção e exportação GPKG/KML
├── run.sh                  # Script de inicialização rápida
├── requirements.txt        # Dependências Python
├── Dockerfile              # Imagem Docker com suporte a GDAL/GeoPandas
├── docker-compose.yml      # Configuração para subida em 1 comando
├── .gitignore              # Regras de exclusão para Git
├── LICENSE                 # Licença MIT
├── templates/
│   └── index.html          # Interface visual completa estilo QGIS Desktop
├── static/
│   ├── css/
│   │   └── qgis-theme.css  # Tema e estilos desktop do QGIS
│   └── js/
│       └── app.js          # Lógica cliente (Leaflet, Three.js, IBGE, Tabela, Arraste)
├── data_cache/             # Cache local de tiles HGT e malhas GeoJSON (ignorado no Git)
└── exports/                # Diretório de arquivos gerados pelo usuário (ignorado no Git)
```

---

## 📄 Licença

Este projeto está sob a licença [MIT](LICENSE). Sinta-se livre para usar, modificar e distribuir.

---

<p align="center">
  Desenvolvido com carinho por <strong>Thiago Quinaia</strong>.
</p>
