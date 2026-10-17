/**
 * DivinoGIS Web - Gerador Topo 3D (SRTM 30m) & Malhas IBGE
 * Client Application Logic
 */

// Global State
let map = null;
let baseLayers = {};
let currentBaseLayer = null;
let currentMode = 'pan'; // 'pan', 'draw_rect', 'identify'

// Layers State
let layersRegistry = {}; // id -> { metadata, overlay, domElement, opacity }
let activeLayerId = null;
let layerCounter = 1;

// AOI State
let currentAoiBounds = null;
let aoiRectangleLayer = null;
let isDrawingAoi = false;
let aoiStartLatLng = null;

// Three.js State
let scene3d = null, camera3d = null, renderer3d = null, mesh3d = null;
let is3dInitialized = false;

// Vector Feature Selection State (for automatic SRTM extraction & clipping)
let selectedVectorFeature = null; // { feature, leafletLayer, layerId, name, geometry }

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  initMap();
  initDockResizer();
  initGlobalListeners();
  initSampleAOI();
  carregarListaUFsIBGE();
  initDraggableDialogs();
});

/**
 * 1. Inicialização do Mapa Leaflet
 */
function initMap() {
  // Configuração dos basemaps
  baseLayers = {
    osm: L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }),
    opentopo: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      maxZoom: 17,
      attribution: '&copy; OpenTopoMap contributors'
    }),
    esri: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: '&copy; Esri World Imagery'
    }),
    carto: L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; CartoDB Positron'
    })
  };

  // Inicializa mapa em São Paulo (relevo variado com serra e planalto)
  map = L.map('map', {
    center: [-23.5505, -46.6333],
    zoom: 11,
    zoomControl: false,
    layers: [baseLayers.osm]
  });
  currentBaseLayer = baseLayers.osm;

  // Zoom control no canto superior esquerdo estilo QGIS
  L.control.zoom({ position: 'topleft' }).addTo(map);

  // Escala no canto inferior esquerdo do mapa
  L.control.scale({ imperial: false, metric: true, position: 'bottomleft' }).addTo(map);

  // Eventos de movimento do mouse para atualizar a barra de status
  map.on('mousemove', (e) => {
    const lat = e.latlng.lat.toFixed(5);
    const lon = e.latlng.lng.toFixed(5);
    const statusCoords = document.getElementById('status-coords');
    if (statusCoords) {
      statusCoords.innerText = `Coordenada: Lat: ${lat}°  Lon: ${lon}°`;
    }

    if (currentMode === 'draw_rect' && isDrawingAoi && aoiStartLatLng) {
      updateAoiDrawing(e.latlng);
    }
  });

  map.on('zoomend', () => {
    updateScaleDisplay();
  });

  // Eventos de clique no mapa
  map.on('mousedown', (e) => {
    if (currentMode === 'draw_rect') {
      startAoiDrawing(e.latlng);
    }
  });

  map.on('mouseup', (e) => {
    if (currentMode === 'draw_rect' && isDrawingAoi) {
      finishAoiDrawing(e.latlng);
    }
  });

  map.on('click', (e) => {
    if (currentMode === 'identify') {
      handleIdentifyElevation(e);
    }
  });

  updateScaleDisplay();
}

/**
 * Atualiza exibição da escala aproximada
 */
function updateScaleDisplay() {
  if (!map) return;
  const zoom = map.getZoom();
  // Escala aproximada para Web Mercator por nível de zoom na latitude média
  const scaleValues = {
    1: '1 : 250 000 000', 2: '1 : 150 000 000', 3: '1 : 70 000 000',
    4: '1 : 35 000 000', 5: '1 : 18 000 000', 6: '1 : 9 000 000',
    7: '1 : 4 500 000', 8: '1 : 2 000 000', 9: '1 : 1 000 000',
    10: '1 : 500 000', 11: '1 : 250 000', 12: '1 : 100 000',
    13: '1 : 50 000', 14: '1 : 25 000', 15: '1 : 10 000',
    16: '1 : 5 000', 17: '1 : 2 500', 18: '1 : 1 000', 19: '1 : 500'
  };
  const scaleText = scaleValues[zoom] || `1 : ${Math.round(591657550 / Math.pow(2, zoom - 1))}`;
  const el = document.getElementById('status-scale');
  if (el) el.innerText = `Escala: ${scaleText}`;
}

/**
 * 2. Modos de Navegação e Ferramentas
 */
function ativarModoPan() {
  currentMode = 'pan';
  map.dragging.enable();
  map.getContainer().style.cursor = '';
  document.getElementById('btn-tool-pan').classList.add('active');
  document.getElementById('btn-draw-rect').classList.remove('active');
  document.getElementById('btn-tool-identify').classList.remove('active');
  document.getElementById('elevation-inspector').style.display = 'none';
  setStatusMsg('Modo Navegação (Pan)');
}

function ativarDesenhoRetangulo() {
  currentMode = 'draw_rect';
  map.dragging.disable();
  map.getContainer().style.cursor = 'crosshair';
  document.getElementById('btn-tool-pan').classList.remove('active');
  document.getElementById('btn-draw-rect').classList.add('active');
  document.getElementById('btn-tool-identify').classList.remove('active');
  document.getElementById('elevation-inspector').style.display = 'none';
  setStatusMsg('Clique e arraste no mapa para definir a Área de Interesse (AOI)');
  showToast('Clique e arraste no mapa para selecionar a área');
}

function ativarModoIdentify() {
  currentMode = 'identify';
  map.dragging.enable();
  map.getContainer().style.cursor = 'help';
  document.getElementById('btn-tool-pan').classList.remove('active');
  document.getElementById('btn-draw-rect').classList.remove('active');
  document.getElementById('btn-tool-identify').classList.add('active');
  setStatusMsg('Clique em qualquer ponto do relevo para inspecionar a elevação');
  showToast('Clique sobre a camada raster para ver a cota em metros');
}

/**
 * 3. Desenho de AOI (Bounding Box)
 */
function startAoiDrawing(latlng) {
  isDrawingAoi = true;
  aoiStartLatLng = latlng;

  if (aoiRectangleLayer) {
    map.removeLayer(aoiRectangleLayer);
    aoiRectangleLayer = null;
  }

  const bounds = L.latLngBounds(latlng, latlng);
  aoiRectangleLayer = L.rectangle(bounds, {
    color: '#1976d2',
    weight: 2,
    dashArray: '4, 4',
    fillColor: '#2196f3',
    fillOpacity: 0.25
  }).addTo(map);
}

function updateAoiDrawing(latlng) {
  if (!isDrawingAoi || !aoiStartLatLng || !aoiRectangleLayer) return;

  const bounds = L.latLngBounds(aoiStartLatLng, latlng);
  aoiRectangleLayer.setBounds(bounds);
  currentAoiBounds = bounds;

  // Calcula dimensões
  const distKmX = (bounds.getNorthEast().distanceTo(L.latLng(bounds.getNorth(), bounds.getWest())) / 1000).toFixed(1);
  const distKmY = (bounds.getNorthEast().distanceTo(L.latLng(bounds.getSouth(), bounds.getEast())) / 1000).toFixed(1);
  const areaKm2 = (distKmX * distKmY).toFixed(1);

  const badge = document.getElementById('map-badge-aoi');
  const badgeInfo = document.getElementById('aoi-badge-info');
  badgeInfo.innerHTML = `<strong>Área AOI:</strong> ${distKmX} km × ${distKmY} km (${areaKm2} km²)`;
  badge.classList.add('show');
}

function finishAoiDrawing(latlng) {
  isDrawingAoi = false;
  if (!aoiStartLatLng) return;

  const bounds = L.latLngBounds(aoiStartLatLng, latlng);
  // Se for um clique único sem arrastar, cria um retângulo padrão de ~8km x 8km
  if (bounds.getNorth() === bounds.getSouth() || bounds.getEast() === bounds.getWest()) {
    const latDelta = 0.04;
    const lonDelta = 0.04;
    currentAoiBounds = L.latLngBounds(
      [latlng.lat - latDelta, latlng.lng - lonDelta],
      [latlng.lat + latDelta, latlng.lng + lonDelta]
    );
    if (aoiRectangleLayer) map.removeLayer(aoiRectangleLayer);
    aoiRectangleLayer = L.rectangle(currentAoiBounds, {
      color: '#1976d2',
      weight: 2,
      dashArray: '4, 4',
      fillColor: '#2196f3',
      fillOpacity: 0.25
    }).addTo(map);
  } else {
    currentAoiBounds = bounds;
  }

  // Volta ao modo Pan após terminar a seleção
  ativarModoPan();

  // Atualiza badge
  const distKmX = (currentAoiBounds.getNorthEast().distanceTo(L.latLng(currentAoiBounds.getNorth(), currentAoiBounds.getWest())) / 1000).toFixed(1);
  const distKmY = (currentAoiBounds.getNorthEast().distanceTo(L.latLng(currentAoiBounds.getSouth(), currentAoiBounds.getEast())) / 1000).toFixed(1);
  const areaKm2 = (distKmX * distKmY).toFixed(1);

  const badge = document.getElementById('map-badge-aoi');
  const badgeInfo = document.getElementById('aoi-badge-info');
  badgeInfo.innerHTML = `<strong>Área Selecionada:</strong> ${distKmX} km × ${distKmY} km (${areaKm2} km²)`;
  badge.classList.add('show');

  setStatusMsg(`AOI definida: ${areaKm2} km². Clique em "Solicitar SRTM 30m" para baixar.`);
}

function limparSelecao() {
  if (aoiRectangleLayer) {
    map.removeLayer(aoiRectangleLayer);
    aoiRectangleLayer = null;
  }
  currentAoiBounds = null;
  document.getElementById('map-badge-aoi').classList.remove('show');
  ativarModoPan();
  setStatusMsg('Seleção limpa.');
}

/**
 * Cria uma AOI inicial de exemplo para o usuário poder testar imediatamente
 */
function initSampleAOI() {
  // Área em São Paulo / Serra da Cantareira
  const sampleBounds = L.latLngBounds([-23.50, -46.68], [-23.40, -46.54]);
  currentAoiBounds = sampleBounds;
  aoiRectangleLayer = L.rectangle(sampleBounds, {
    color: '#1976d2',
    weight: 2,
    dashArray: '4, 4',
    fillColor: '#2196f3',
    fillOpacity: 0.2
  }).addTo(map);

  const distKmX = (sampleBounds.getNorthEast().distanceTo(L.latLng(sampleBounds.getNorth(), sampleBounds.getWest())) / 1000).toFixed(1);
  const distKmY = (sampleBounds.getNorthEast().distanceTo(L.latLng(sampleBounds.getSouth(), sampleBounds.getEast())) / 1000).toFixed(1);
  const areaKm2 = (distKmX * distKmY).toFixed(1);

  const badge = document.getElementById('map-badge-aoi');
  const badgeInfo = document.getElementById('aoi-badge-info');
  badgeInfo.innerHTML = `<strong>Área de Exemplo:</strong> ${distKmX} km × ${distKmY} km (${areaKm2} km²)`;
  badge.classList.add('show');
}

/**
 * 4. Solicitação do SRTM 30m ao Backend
 */
async function solicitarSRTM() {
  if (!currentAoiBounds) {
    alert("Por favor, defina uma Área de Interesse (AOI) no mapa primeiro usando a ferramenta 'Definir AOI'.");
    ativarDesenhoRetangulo();
    return;
  }

  const minLat = currentAoiBounds.getSouth();
  const maxLat = currentAoiBounds.getNorth();
  const minLon = currentAoiBounds.getWest();
  const maxLon = currentAoiBounds.getEast();

  const colormap = document.getElementById('select-colormap').value;
  const hillshade = document.getElementById('check-hillshade').checked;
  const btn = document.getElementById('btn-get-srtm');

  btn.disabled = true;
  btn.innerHTML = `<span style="display:inline-block; animation:spin 1s infinite linear;">⚙️</span> Processando...`;
  simularProgressoPasso("Baixando dados SRTM 30m e gerando GeoTIFF...", 3500);
  showToast("Consultando NASA SRTM 30m na nuvem...");

  try {
    const payload = {
      min_lat: minLat,
      min_lon: minLon,
      max_lat: maxLat,
      max_lon: maxLon,
      name: `SRTM_30m_AOI_${layerCounter++}`,
      colormap: colormap,
      hillshade: hillshade
    };

    const resp = await fetch('/api/srtm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await resp.json();

    if (!resp.ok || data.error) {
      throw new Error(data.error || "Falha ao processar o SRTM.");
    }

    // Camada gerada com sucesso!
    adicionarCamadaRaster(data.layer);
    showToast(`Camada "${data.layer.name}" adicionada ao painel de camadas! Clique com o botão direito nela para baixar em .tiff`);
    finalizarProgresso(`Pronto. Camada ${data.layer.name} gerada com sucesso (${data.layer.stats.min}m a ${data.layer.stats.max}m).`);

  } catch (err) {
    console.error(err);
    alert(`Erro ao solicitar SRTM 30m: ${err.message}`);
    cancelarProgresso("Erro ao processar SRTM.");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
      <span>Solicitar SRTM 30m</span>
    `;
  }
}

/**
 * 5. Adiciona Camada Raster ao Mapa e ao Painel "Camadas"
 */
function adicionarCamadaRaster(layer) {
  // Cria Leaflet ImageOverlay com a imagem de pré-visualização georreferenciada
  const overlay = L.imageOverlay(layer.preview_url, layer.leaflet_bounds, {
    opacity: 0.9,
    interactive: true
  }).addTo(map);

  // Registra no estado global
  layersRegistry[layer.id] = {
    type: 'raster',
    metadata: layer,
    overlay: overlay,
    opacity: 0.9
  };
  activeLayerId = layer.id;

  // Opcional: ajusta zoom do mapa para a camada recém-adicionada
  map.fitBounds(layer.leaflet_bounds, { padding: [20, 20] });

  // Renderiza o item na árvore de camadas do QGIS (lado esquerdo)
  renderizarItemCamada(layer);
}

/**
 * Renderiza o elemento HTML da camada no painel esquerdo "Camadas"
 */
function renderizarItemCamada(layer) {
  const container = document.getElementById('layers-tree-container');

  // Remove seleção ativa anterior
  document.querySelectorAll('.layer-item').forEach(el => el.classList.remove('active'));

  const item = document.createElement('div');
  item.className = 'layer-item active';
  item.id = `layer-item-${layer.id}`;
  item.dataset.id = layer.id;

  // Gradiente CSS para a legenda do relevo
  const gradientCss = "linear-gradient(90deg, #338833 0%, #ffff77 35%, #ff8833 70%, #ffffff 100%)";

  item.innerHTML = `
    <div class="layer-header-row">
      <input type="checkbox" class="layer-checkbox" id="check-${layer.id}" checked>
      <div class="layer-type-icon" title="Camada Raster QGIS">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <rect x="2" y="2" width="20" height="20" rx="2" fill="#e8f5e9" stroke="#4caf50" stroke-width="1.5"></rect>
          <path d="M4 18l4-5 3 3 5-7 4 5" stroke="#2e7d32" stroke-width="1.8" fill="none"></path>
          <circle cx="7" cy="8" r="1.5" fill="#f57c00"></circle>
        </svg>
      </div>
      <span class="layer-name" title="${layer.name} (${layer.stats.min}m a ${layer.stats.max}m)">
        ${layer.name}
        ${layer.is_clipped ? '<span style="font-size:9px; background:#e3f2fd; color:#1565c0; border:1px solid #bbdefb; border-radius:2px; padding:0 3px; margin-left:3px; vertical-align:middle;" title="Recortado pela feição vetorial">✂️ Recorte</span>' : ''}
      </span>
      <span class="layer-quick-download" title="Baixar diretamente em GeoTIFF (.tiff)" onclick="event.stopPropagation(); baixarGeoTiff('${layer.id}')">
        📥 .tiff
      </span>
    </div>
    <div class="layer-legend">
      <div class="legend-ramp-bar" style="background: ${gradientCss};"></div>
      <div class="legend-values">
        <span>Min: ${layer.stats.min} m</span>
        <span>Méd: ${layer.stats.mean} m</span>
        <span>Max: ${layer.stats.max} m</span>
      </div>
    </div>
  `;

  // Salva referência do elemento DOM
  layersRegistry[layer.id].domElement = item;

  // Clique simples: define como camada ativa
  item.addEventListener('click', (e) => {
    document.querySelectorAll('.layer-item').forEach(el => el.classList.remove('active'));
    item.classList.add('active');
    activeLayerId = layer.id;
  });

  // Checkbox de visibilidade
  const check = item.querySelector(`#check-${layer.id}`);
  check.addEventListener('change', (e) => {
    e.stopPropagation();
    toggleLayerVisibility(layer.id, check.checked);
  });

  // ==============================================================
  // REQUISITO CRÍTICO: MENU DE CONTEXTO (CLIQUE COM BOTÃO DIREITO)
  // ==============================================================
  item.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    e.stopPropagation();

    // Define como ativa
    document.querySelectorAll('.layer-item').forEach(el => el.classList.remove('active'));
    item.classList.add('active');
    activeLayerId = layer.id;

    // Abre o menu de contexto na posição do mouse
    abrirContextMenu(e.clientX, e.clientY, layer.id);
  });

  // Insere no topo da lista (acima do basemap)
  const basemapItem = document.getElementById('layer-item-basemap');
  container.insertBefore(item, basemapItem);
}

/**
 * 6. Menu de Contexto (Right-Click) Estilo QGIS
 */
function abrirContextMenu(x, y, layerId) {
  const menu = document.getElementById('layer-context-menu');
  if (!menu) return;

  const reg = layersRegistry[layerId];
  const isVector = reg && reg.type === 'vector';

  // Alterna opções de menu específicas para raster vs vetorial
  menu.querySelectorAll('.cm-raster-only').forEach(el => {
    el.style.display = isVector ? 'none' : 'flex';
  });
  menu.querySelectorAll('.cm-vector-only').forEach(el => {
    el.style.display = isVector ? 'flex' : 'none';
  });

  // Ajusta se estiver próximo da borda da janela
  const winWidth = window.innerWidth;
  const winHeight = window.innerHeight;
  const menuWidth = 240;
  const menuHeight = isVector ? 220 : 270;

  let left = x;
  let top = y;

  if (x + menuWidth > winWidth) left = winWidth - menuWidth - 10;
  if (y + menuHeight > winHeight) top = winHeight - menuHeight - 10;

  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;
  menu.classList.add('show');
}

function fecharContextMenu() {
  const menu = document.getElementById('layer-context-menu');
  if (menu) menu.classList.remove('show');
}

// Ações do Menu de Contexto
function contextDownloadTiff() {
  fecharContextMenu();
  if (activeLayerId) {
    baixarGeoTiff(activeLayerId);
  }
}

function contextZoomToLayer() {
  fecharContextMenu();
  if (activeLayerId && layersRegistry[activeLayerId]) {
    const reg = layersRegistry[activeLayerId];
    if (reg.type === 'vector' && reg.layerGroup) {
      if (reg.layerGroup.getBounds().isValid()) {
        map.fitBounds(reg.layerGroup.getBounds(), { padding: [25, 25] });
      }
    } else if (reg.metadata && reg.metadata.leaflet_bounds) {
      map.fitBounds(reg.metadata.leaflet_bounds, { padding: [25, 25] });
    }
    setStatusMsg(`Aproximado para a camada ${reg.metadata.name}`);
  }
}

function contextToggleVisibility() {
  fecharContextMenu();
  if (activeLayerId && layersRegistry[activeLayerId]) {
    const reg = layersRegistry[activeLayerId];
    const target = reg.overlay || reg.layerGroup;
    if (target) {
      const isVisible = map.hasLayer(target);
      toggleLayerVisibility(activeLayerId, !isVisible);
      const check = document.getElementById(`check-${activeLayerId}`);
      if (check) check.checked = !isVisible;
    }
  }
}

function contextChangeOpacity() {
  fecharContextMenu();
  if (!activeLayerId || !layersRegistry[activeLayerId]) return;
  const curOpacity = Math.round(layersRegistry[activeLayerId].opacity * 100);
  const input = prompt("Defina a opacidade da camada (0 a 100%):", curOpacity);
  if (input !== null) {
    const val = parseInt(input, 10);
    if (!isNaN(val) && val >= 0 && val <= 100) {
      const op = val / 100.0;
      layersRegistry[activeLayerId].opacity = op;
      if (layersRegistry[activeLayerId].overlay && layersRegistry[activeLayerId].overlay.setOpacity) {
        layersRegistry[activeLayerId].overlay.setOpacity(op);
      }
      showToast(`Opacidade ajustada para ${val}%`);
    }
  }
}

function contextOpenProperties() {
  fecharContextMenu();
  if (activeLayerId && layersRegistry[activeLayerId]) {
    const reg = layersRegistry[activeLayerId];
    if (reg.type === 'vector') {
      abrirTabelaAtributos(activeLayerId);
    } else {
      abrirModalPropriedades(reg.metadata);
    }
  }
}

function contextView3D() {
  fecharContextMenu();
  abrirModal3D();
}

function contextDeleteLayer() {
  fecharContextMenu();
  if (activeLayerId) {
    removerCamada(activeLayerId);
  }
}

/**
 * 7. Download do arquivo GeoTIFF (.tiff)
 */
function baixarGeoTiff(layerId) {
  const layer = layersRegistry[layerId];
  if (!layer) return;

  const downloadUrl = `/api/download/${layerId}.tif`;
  iniciarProgresso(`Baixando GeoTIFF: ${layer.metadata.name}.tif ...`, 80);
  showToast(`Baixando GeoTIFF: ${layer.metadata.name}.tif ...`);

  // Dispara o download nativo no navegador
  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = `${layer.metadata.name}.tif`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  finalizarProgresso(`Pronto. Download do GeoTIFF iniciado: ${layer.metadata.name}.tif`);
}

function baixarCamadaAtivaTiff() {
  if (activeLayerId) {
    baixarGeoTiff(activeLayerId);
  } else {
    alert("Selecione uma camada raster na lista de camadas primeiro.");
  }
}

function baixarGeoTiffModal() {
  if (activeLayerId) {
    baixarGeoTiff(activeLayerId);
    fecharModalPropriedades();
  }
}

/**
 * 8. Gerenciamento de Camadas (Visibilidade e Remoção)
 */
function toggleLayerVisibility(layerId, isVisible) {
  const reg = layersRegistry[layerId];
  if (!reg) return;

  const target = reg.overlay || reg.layerGroup;
  if (!target) return;

  if (isVisible) {
    if (!map.hasLayer(target)) map.addLayer(target);
  } else {
    if (map.hasLayer(target)) map.removeLayer(target);
  }
}

function toggleBasemapVisivel(isVisible) {
  if (currentBaseLayer) {
    if (isVisible) {
      if (!map.hasLayer(currentBaseLayer)) map.addLayer(currentBaseLayer);
    } else {
      if (map.hasLayer(currentBaseLayer)) map.removeLayer(currentBaseLayer);
    }
  }
}

function trocarBasemap(type) {
  if (currentBaseLayer && map.hasLayer(currentBaseLayer)) {
    map.removeLayer(currentBaseLayer);
  }
  currentBaseLayer = baseLayers[type] || baseLayers.osm;
  map.addLayer(currentBaseLayer);
  setStatusMsg(`Basemap alterado para: ${type.toUpperCase()}`);
}

function removerCamada(layerId) {
  if (!confirm("Deseja realmente remover esta camada do projeto?")) return;

  const reg = layersRegistry[layerId];
  if (reg) {
    const target = reg.overlay || reg.layerGroup;
    if (target && map.hasLayer(target)) map.removeLayer(target);
    if (reg.domElement) reg.domElement.remove();
    delete layersRegistry[layerId];
    if (reg.type === 'raster') {
      fetch(`/api/layers/${layerId}`, { method: 'DELETE' }).catch(console.error);
    }
    activeLayerId = null;
    showToast("Camada removida.");
    setStatusMsg("Camada removida.");
  }
}

function removerCamadaAtiva() {
  if (activeLayerId) {
    removerCamada(activeLayerId);
  } else {
    alert("Nenhuma camada selecionada.");
  }
}

function limparTodasCamadas() {
  if (!confirm("Deseja remover todas as camadas geradas?")) return;
  Object.keys(layersRegistry).forEach(id => {
    const reg = layersRegistry[id];
    const target = reg.overlay || reg.layerGroup;
    if (target && map.hasLayer(target)) map.removeLayer(target);
    if (reg.domElement) reg.domElement.remove();
    delete layersRegistry[id];
    if (reg.type === 'raster') {
      fetch(`/api/layers/${id}`, { method: 'DELETE' }).catch(console.error);
    }
  });
  limparSelecao();
  activeLayerId = null;
  showToast("Todas as camadas foram removidas.");
}

function toggleVisibilidadeTodas() {
  const anyVisible = Object.values(layersRegistry).some(r => {
    const target = r.overlay || r.layerGroup;
    return target && map.hasLayer(target);
  });
  const newVisibility = !anyVisible;
  Object.keys(layersRegistry).forEach(id => {
    toggleLayerVisibility(id, newVisibility);
    const check = document.getElementById(`check-${id}`);
    if (check) check.checked = newVisibility;
  });
}

function toggleExpandirTodasCamadas() {
  const legends = document.querySelectorAll('.layer-legend');
  legends.forEach(l => {
    l.style.display = (l.style.display === 'none') ? 'flex' : 'none';
  });
}

function filtrarCamadas(text) {
  const q = text.toLowerCase().trim();
  document.querySelectorAll('.layer-item').forEach(item => {
    if (item.id === 'layer-item-basemap') return;
    const name = item.querySelector('.layer-name').innerText.toLowerCase();
    item.style.display = name.includes(q) ? 'flex' : 'none';
  });
}

/**
 * 9. Consulta de Elevação (Ferramenta Identificar Feição)
 */
async function handleIdentifyElevation(e) {
  if (!activeLayerId || !layersRegistry[activeLayerId]) {
    // Tenta pegar a primeira camada se houver
    const firstId = Object.keys(layersRegistry)[0];
    if (firstId) activeLayerId = firstId;
    else {
      showToast("Gere uma camada SRTM primeiro para consultar elevações.");
      return;
    }
  }

  const lat = e.latlng.lat;
  const lon = e.latlng.lng;
  const popup = document.getElementById('elevation-inspector');
  const valDisplay = document.getElementById('elev-val-display');
  const coordsDisplay = document.getElementById('elev-coords-display');

  // Posiciona popup
  popup.style.left = `${e.containerPoint.x + 15}px`;
  popup.style.top = `${e.containerPoint.y - 15}px`;
  popup.style.display = 'block';
  valDisplay.innerText = 'Consultando...';
  coordsDisplay.innerText = `Lat: ${lat.toFixed(4)} | Lon: ${lon.toFixed(4)}`;

  try {
    const resp = await fetch(`/api/elevation?layer_id=${activeLayerId}&lat=${lat}&lon=${lon}`);
    const data = await resp.json();
    if (data.success && data.elevation !== null) {
      valDisplay.innerHTML = `<span style="color:#2e7d32; font-size:14px;">${data.elevation.toFixed(1)} m</span>`;
      setStatusMsg(`Ponto consultado: Elevação de ${data.elevation.toFixed(1)} m`);
    } else {
      valDisplay.innerHTML = `<span style="color:#888;">Fora da camada</span>`;
    }
  } catch (err) {
    valDisplay.innerText = 'Erro na leitura';
  }
}

/**
 * 10. Localizador / Busca de Lugares (Nominatim OSM)
 */
async function buscarLocalidade(query) {
  if (!query || !query.trim()) return;
  setStatusMsg(`Pesquisando por: "${query}"...`);
  try {
    const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const results = await resp.json();
    if (results && results.length > 0) {
      const top = results[0];
      const lat = parseFloat(top.lat);
      const lon = parseFloat(top.lon);
      map.flyTo([lat, lon], 12);
      setStatusMsg(`Localizado: ${top.display_name}`);
      showToast(`Localizado: ${top.display_name.split(',')[0]}`);
    } else {
      alert(`Localidade "${query}" não encontrada.`);
      setStatusMsg("Localidade não encontrada.");
    }
  } catch (e) {
    console.error(e);
  }
}

/**
 * 11. Modal de Propriedades da Camada
 */
function abrirModalPropriedades(layer) {
  document.getElementById('prop-dialog-title').innerText = `Propriedades da Camada - ${layer.name}`;
  document.getElementById('prop-name').innerText = layer.name;
  document.getElementById('prop-crs').innerText = layer.crs;
  document.getElementById('prop-extent').innerText =
    `Norte: ${layer.bounds.max_lat.toFixed(4)}°, Sul: ${layer.bounds.min_lat.toFixed(4)}°, ` +
    `Leste: ${layer.bounds.max_lon.toFixed(4)}°, Oeste: ${layer.bounds.min_lon.toFixed(4)}°`;
  document.getElementById('prop-dimensions').innerText =
    `${layer.dimensions.width} colunas × ${layer.dimensions.height} linhas (Total: ${(layer.dimensions.width * layer.dimensions.height).toLocaleString()} pixels)`;
  document.getElementById('prop-min-elev').innerText = `${layer.stats.min} metros`;
  document.getElementById('prop-max-elev').innerText = `${layer.stats.max} metros`;
  document.getElementById('prop-mean-elev').innerText = `${layer.stats.mean} metros`;
  document.getElementById('prop-file-size').innerText = `${(layer.file_size / 1024).toFixed(1)} KB (GeoTIFF Comprimido DEFLATE)`;

  document.getElementById('prop-meta-raw').innerText = JSON.stringify(layer, null, 2);

  document.getElementById('modal-properties').classList.add('show');
}

function fecharModalPropriedades() {
  document.getElementById('modal-properties').classList.remove('show');
}

function abrirPropriedadesCamadaAtiva() {
  if (activeLayerId && layersRegistry[activeLayerId]) {
    abrirModalPropriedades(layersRegistry[activeLayerId].metadata);
  } else {
    alert("Selecione uma camada raster para ver as propriedades.");
  }
}

function trocarAbaPropriedades(tabId) {
  document.querySelectorAll('.dialog-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');

  if (tabId === 'tab-info') {
    document.querySelectorAll('.dialog-tab')[0].classList.add('active');
    document.getElementById('tab-info').style.display = 'block';
  } else {
    document.querySelectorAll('.dialog-tab')[1].classList.add('active');
    document.getElementById('tab-meta').style.display = 'block';
  }
}

let controls3d = null;
let anim3dFrameId = null;

/**
 * 12. Visualizador 3D (Three.js com Elevação Real SRTM 30m)
 */
function abrirModal3D() {
  if (!activeLayerId || !layersRegistry[activeLayerId]) {
    const keys = Object.keys(layersRegistry);
    if (keys.length > 0) activeLayerId = keys[0];
    else {
      alert("Gere uma camada SRTM primeiro para visualizar em 3D.");
      return;
    }
  }

  const layer = layersRegistry[activeLayerId].metadata;
  document.getElementById('modal-3d').classList.add('show');
  
  // Reseta o slider para 1.5x
  const slider = document.getElementById('vert-exag-range');
  if (slider) slider.value = "1.5";
  const valLabel = document.getElementById('vert-exag-val');
  if (valLabel) valLabel.innerText = "1.5x";
  const wireCheck = document.getElementById('check-wireframe');
  if (wireCheck) wireCheck.checked = false;

  init3DScene(layer);
}

function fecharModal3D() {
  document.getElementById('modal-3d').classList.remove('show');
  if (anim3dFrameId) {
    cancelAnimationFrame(anim3dFrameId);
    anim3dFrameId = null;
  }
}

async function init3DScene(layer) {
  const container = document.getElementById('viewer3d-container');
  const loading = document.getElementById('viewer3d-loading');
  if (loading) loading.style.display = 'block';

  container.innerHTML = '';
  if (anim3dFrameId) {
    cancelAnimationFrame(anim3dFrameId);
    anim3dFrameId = null;
  }

  const width = container.clientWidth || 760;
  const height = container.clientHeight || 400;

  // 1. Configura cena e câmera Three.js
  scene3d = new THREE.Scene();
  scene3d.background = new THREE.Color(0x15181c);

  camera3d = new THREE.PerspectiveCamera(45, width / height, 0.5, 2000);
  camera3d.position.set(0, -55, 45);
  camera3d.up.set(0, 0, 1); // Eixo Z para cima (Convenção SIG/Topografia)

  renderer3d = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer3d.setSize(width, height);
  renderer3d.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer3d.shadowMap.enabled = true;
  container.appendChild(renderer3d.domElement);

  // 2. Controles de Órbita (OrbitControls)
  if (typeof THREE.OrbitControls !== 'undefined') {
    controls3d = new THREE.OrbitControls(camera3d, renderer3d.domElement);
    controls3d.enableDamping = true;
    controls3d.dampingFactor = 0.08;
    controls3d.target.set(0, 0, 5);
    controls3d.maxPolarAngle = Math.PI / 2 + 0.05; // Evita olhar muito por baixo do chão
    controls3d.minDistance = 10;
    controls3d.maxDistance = 300;
  }

  // 3. Iluminação realista de relevo
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
  scene3d.add(ambientLight);

  const sunLight = new THREE.DirectionalLight(0xfff8ee, 0.95);
  sunLight.position.set(-60, -60, 90);
  scene3d.add(sunLight);

  const fillLight = new THREE.DirectionalLight(0xb0c4de, 0.4);
  fillLight.position.set(60, 60, -20);
  scene3d.add(fillLight);

  // Eixo de referência sutil ou grid de base
  const gridHelper = new THREE.GridHelper(80, 20, 0x334455, 0x222a33);
  gridHelper.rotation.x = Math.PI / 2;
  gridHelper.position.z = -0.2;
  scene3d.add(gridHelper);

  try {
    // 4. Busca matriz de elevação real no backend
    const resp = await fetch(`/api/elevation-grid/${layer.id}`);
    const gridData = await resp.json();

    if (!resp.ok || gridData.error) {
      throw new Error(gridData.error || "Erro ao carregar malha de elevação");
    }

    const nx = gridData.nx;
    const ny = gridData.ny;
    const elevations = gridData.elevations;
    const minElev = gridData.min_elev;
    const maxElev = gridData.max_elev;
    const rangeElev = Math.max(1.0, maxElev - minElev);

    // Dimensões do plano proporcional à extensão geográfica
    const planeW = 60.0;
    const planeH = 60.0 * (ny / nx);

    // Geometria com resolução exata da matriz
    const geom = new THREE.PlaneGeometry(planeW, planeH, nx - 1, ny - 1);
    const pos = geom.attributes.position;

    // Altura base do relevo antes do fator de exagero
    const BASE_RELIEF_HEIGHT = 12.0;

    // Aplica os valores reais de elevação ao eixo Z de cada vértice
    for (let i = 0; i < elevations.length && i < pos.count; i++) {
      const zNorm = (elevations[i] - minElev) / rangeElev;
      pos.array[i * 3 + 2] = zNorm * BASE_RELIEF_HEIGHT;
    }

    geom.computeVertexNormals();
    pos.needsUpdate = true;

    // 5. Carrega textura (shaded relief / rampa de cores do DEM)
    const textureLoader = new THREE.TextureLoader();
    textureLoader.load(layer.preview_url, (texture) => {
      texture.minFilter = THREE.LinearFilter;
      texture.magFilter = THREE.LinearFilter;

      const mat = new THREE.MeshStandardMaterial({
        map: texture,
        roughness: 0.65,
        metalness: 0.05,
        flatShading: false,
        side: THREE.DoubleSide,
        transparent: true,
        alphaTest: 0.05
      });

      mesh3d = new THREE.Mesh(geom, mat);
      
      // Aplica o exagero vertical inicial (1.5x)
      const initialExag = parseFloat(document.getElementById('vert-exag-range').value || "1.5");
      mesh3d.scale.z = initialExag;

      scene3d.add(mesh3d);

      if (loading) loading.style.display = 'none';
      animate3D();
    }, undefined, (err) => {
      console.error("Erro ao carregar textura:", err);
      // Fallback para material básico sem textura
      const mat = new THREE.MeshStandardMaterial({
        color: 0x4caf50,
        roughness: 0.7,
        side: THREE.DoubleSide
      });
      mesh3d = new THREE.Mesh(geom, mat);
      mesh3d.scale.z = 1.5;
      scene3d.add(mesh3d);
      if (loading) loading.style.display = 'none';
      animate3D();
    });

  } catch (err) {
    console.error("Erro na cena 3D:", err);
    if (loading) loading.innerHTML = `<span style="color:#ff6b6b;">Erro: ${err.message}</span>`;
  }
}

function animate3D() {
  if (!document.getElementById('modal-3d').classList.contains('show')) return;
  anim3dFrameId = requestAnimationFrame(animate3D);

  if (controls3d) {
    controls3d.update();
  }

  if (renderer3d && scene3d && camera3d) {
    renderer3d.render(scene3d, camera3d);
  }
}

/**
 * Atualiza dinamicamente o exagero vertical do relevo 3D
 */
function atualizarExagero3D(val) {
  const num = parseFloat(val);
  const label = document.getElementById('vert-exag-val');
  if (label) label.innerText = `${num.toFixed(1)}x`;

  if (mesh3d) {
    // Altera a escala no eixo Z dos vértices onde as alturas reais estão armazenadas!
    mesh3d.scale.z = num;
  }
}

/**
 * Alterna modo de visualização entre malha (wireframe) e superfície texturizada
 */
function toggleWireframe3D(isWireframe) {
  if (mesh3d && mesh3d.material) {
    mesh3d.material.wireframe = isWireframe;
  }
}

/**
 * Reseta a câmera 3D para a posição padrão de visão aérea/perspectiva
 */
function resetarCamera3D() {
  if (camera3d && controls3d) {
    camera3d.position.set(0, -55, 45);
    camera3d.up.set(0, 0, 1);
    controls3d.target.set(0, 0, 5);
    controls3d.update();
  }
}

/**
 * 13. Menus Suspensos e Modais Globais
 */
function toggleMenu(menuId) {
  const menu = document.getElementById(menuId);
  const isShown = menu.classList.contains('show');
  fecharTodosMenus();
  if (!isShown) menu.classList.add('show');
}

function fecharTodosMenus() {
  document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('show'));
}

function abrirSobre() {
  document.getElementById('modal-sobre').classList.add('show');
}

function fecharModalSobre() {
  document.getElementById('modal-sobre').classList.remove('show');
}

function zoomIn() { map.zoomIn(); }
function zoomOut() { map.zoomOut(); }
function zoomExtensaoTotal() {
  if (currentAoiBounds) map.fitBounds(currentAoiBounds);
  else map.setView([-23.5505, -46.6333], 10);
}

function novoProjeto() {
  if (confirm("Criar novo projeto? As camadas atuais serão limpas.")) {
    limparTodasCamadas();
  }
}

function exportarMapaPng() {
  alert("Para salvar o mapa atual, use a captura de tela do navegador ou clique com o botão direito na camada raster e selecione 'Salvar Como GeoTIFF (.tiff)' para o raster georreferenciado.");
}

function setStatusMsg(msg) {
  const el = document.getElementById('status-msg');
  if (el) el.innerText = msg;
}

/**
 * ==============================================================================
 * Sistema Padronizado de Barra de Progresso QGIS no Rodapé
 * ==============================================================================
 */
let progressInterval = null;

function iniciarProgresso(texto, modo = 'indeterminate') {
  const barContainer = document.getElementById('qgis-progress-widget');
  const barFill = document.getElementById('qgis-progress-fill');
  const barLabel = document.getElementById('qgis-progress-text');
  const statusMsg = document.getElementById('status-msg');

  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }

  if (barContainer) {
    barContainer.style.display = 'flex';
  }
  if (barLabel) {
    barLabel.innerText = texto || 'Processando...';
  }
  if (statusMsg) {
    statusMsg.innerText = texto || 'Processando...';
    statusMsg.style.color = '#1565c0';
  }

  if (modo === 'indeterminate') {
    if (barFill) {
      barFill.classList.add('striped-animated');
      barFill.style.width = '100%';
    }
  } else {
    atualizarProgresso(typeof modo === 'number' ? modo : 10, texto);
  }
}

function atualizarProgresso(porcentagem, texto) {
  const barContainer = document.getElementById('qgis-progress-widget');
  const barFill = document.getElementById('qgis-progress-fill');
  const barLabel = document.getElementById('qgis-progress-text');
  const statusMsg = document.getElementById('status-msg');

  if (barContainer) barContainer.style.display = 'flex';
  if (barFill) {
    barFill.classList.remove('striped-animated');
    barFill.style.width = `${Math.min(100, Math.max(0, porcentagem))}%`;
  }
  const pctStr = `${Math.round(porcentagem)}%`;
  if (barLabel) {
    barLabel.innerText = texto ? `${texto} (${pctStr})` : pctStr;
  }
  if (texto && statusMsg) {
    statusMsg.innerText = texto;
  }
}

function simularProgressoPasso(texto, duracaoAproxMs = 3500) {
  iniciarProgresso(texto, 12);
  let atual = 12;
  const intervaloMs = 120;
  const incremento = (88 - 12) / (duracaoAproxMs / intervaloMs);

  progressInterval = setInterval(() => {
    atual = Math.min(90, atual + incremento);
    atualizarProgresso(atual, texto);
  }, intervaloMs);
}

function finalizarProgresso(msgSucesso = 'Pronto') {
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }

  const barContainer = document.getElementById('qgis-progress-widget');
  const barFill = document.getElementById('qgis-progress-fill');
  const barLabel = document.getElementById('qgis-progress-text');
  const statusMsg = document.getElementById('status-msg');

  if (barFill) {
    barFill.classList.remove('striped-animated');
    barFill.style.width = '100%';
  }
  if (barLabel) {
    barLabel.innerText = '100% Concluído';
  }
  if (statusMsg) {
    statusMsg.innerText = msgSucesso;
    statusMsg.style.color = '#2e6929';
  }

  setTimeout(() => {
    if (!progressInterval && barContainer) {
      barContainer.style.display = 'none';
      if (barFill) barFill.style.width = '0%';
    }
  }, 1400);
}

function cancelarProgresso(msgErro = 'Operação cancelada.') {
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
  const barContainer = document.getElementById('qgis-progress-widget');
  const statusMsg = document.getElementById('status-msg');
  if (barContainer) barContainer.style.display = 'none';
  if (statusMsg) {
    statusMsg.innerText = msgErro;
    statusMsg.style.color = '#c62828';
  }
}

function showToast(msg) {
  const toast = document.getElementById('qgis-toast');
  toast.innerText = msg;
  toast.style.display = 'block';
  setTimeout(() => { toast.style.display = 'none'; }, 3500);
}

function adicionarGrupo() {
  const name = prompt("Nome do novo grupo de camadas:", "Novo Grupo");
  if (name) {
    showToast(`Grupo "${name}" criado.`);
  }
}

/**
 * Redimensionamento do painel esquerdo (Dock Resizer)
 */
function initDockResizer() {
  const resizer = document.getElementById('dock-resizer');
  const dock = document.getElementById('dock-layers');
  let isResizing = false;

  resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    document.body.style.cursor = 'col-resize';
  });

  window.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const newWidth = Math.max(180, Math.min(500, e.clientX));
    dock.style.width = `${newWidth}px`;
    map.invalidateSize();
  });

  window.addEventListener('mouseup', () => {
    if (isResizing) {
      isResizing = false;
      document.body.style.cursor = '';
      map.invalidateSize();
    }
  });
}

/**
 * Listeners globais para fechar menus ao clicar fora
 */
function initGlobalListeners() {
  window.addEventListener('click', (e) => {
    if (!e.target.closest('.menu-item')) {
      fecharTodosMenus();
    }
    if (!e.target.closest('#layer-context-menu')) {
      fecharContextMenu();
    }
  });
}

/**
 * 14. Exportação de Relevo para STL (Impressão 3D e CAD)
 */
let currentStlLayer = null;
let currentStlRealWidthM = 1000.0;
let currentStlRealHeightM = 1000.0;
let currentStlDeltaZM = 100.0;

function getLayerRealWorldMeters(bounds) {
  const minLat = bounds.min_lat;
  const maxLat = bounds.max_lat;
  const minLon = bounds.min_lon;
  const maxLon = bounds.max_lon;

  const midLat = (minLat + maxLat) / 2.0;
  const latRad = (midLat * Math.PI) / 180.0;

  const mPerDegLat = 111132.92 - 559.82 * Math.cos(2 * latRad);
  const mPerDegLon = 111412.84 * Math.cos(latRad);

  const heightM = (maxLat - minLat) * mPerDegLat;
  const widthM = (maxLon - minLon) * mPerDegLon;

  return { widthM: Math.max(1.0, widthM), heightM: Math.max(1.0, heightM) };
}

function contextExportSTL() {
  fecharContextMenu();
  abrirModalSTL();
}

function abrirModalSTL() {
  if (!activeLayerId || !layersRegistry[activeLayerId]) {
    const keys = Object.keys(layersRegistry);
    if (keys.length > 0) activeLayerId = keys[0];
    else {
      alert("Gere uma camada SRTM primeiro para exportar para STL.");
      return;
    }
  }

  currentStlLayer = layersRegistry[activeLayerId].metadata;
  const nameEl = document.getElementById('stl-layer-name');
  if (nameEl) nameEl.innerText = currentStlLayer.name;

  const dims = getLayerRealWorldMeters(currentStlLayer.bounds);
  currentStlRealWidthM = dims.widthM;
  currentStlRealHeightM = dims.heightM;
  currentStlDeltaZM = Math.max(1.0, currentStlLayer.stats.max - currentStlLayer.stats.min);

  document.getElementById('modal-stl').classList.add('show');
  atualizarCalculosSTL();
}

function fecharModalSTL() {
  document.getElementById('modal-stl').classList.remove('show');
}

function selecionarPresetEscala(val) {
  if (val !== 'custom') {
    document.getElementById('stl-scale-input').value = val;
  }
  atualizarCalculosSTL();
}

function onCustomScaleInput(val) {
  const select = document.getElementById('stl-scale-preset');
  if (select) select.value = 'custom';
  atualizarCalculosSTL();
}

function ajustarEscalaPorLargura(targetWidthMm) {
  const scale = Math.round((currentStlRealWidthM * 1000.0) / targetWidthMm);
  document.getElementById('stl-scale-input').value = scale;
  const select = document.getElementById('stl-scale-preset');
  if (select) select.value = 'custom';
  atualizarCalculosSTL();
  showToast(`Escala ajustada para 1 : ${scale.toLocaleString('pt-BR')} (${targetWidthMm} mm de largura)`);
}

function atualizarExageroSTL(val) {
  const num = parseFloat(val);
  document.getElementById('stl-exag-range').value = num;
  document.getElementById('stl-exag-val').innerText = `${num.toFixed(1)}x`;
  atualizarCalculosSTL();
}

function atualizarSuavizacaoSTL(val) {
  const num = parseFloat(val);
  const labels = {
    "0.0": "0.0 (Topografia Pura / Sem Suavização - Padrão)",
    "0.5": "0.5 (Muito Leve)",
    "1.0": "1.0 (Leve)",
    "1.5": "1.5 (Suave)",
    "2.0": "2.0 (Média)",
    "2.5": "2.5 (Acentuada)",
    "3.0": "3.0 (Forte)"
  };
  const label = labels[num.toFixed(1)] || `${num.toFixed(1)}`;
  document.getElementById('stl-smooth-val').innerText = label;
}

function atualizarResolucaoSTL() {
  const sel = document.getElementById('stl-res-select');
  if (!sel) return;
  const val = parseInt(sel.value) || 1000;
  const labels = {
    1400: "Ultra (~0.15mm - Máximo Detalhe)",
    1000: "Alta (~0.2mm - Padrão DEMto3D)",
    600: "Média (~0.4mm - Mais Leve)",
    300: "Rápida (~0.8mm - Prévia)"
  };
  const el = document.getElementById('stl-res-val');
  if (el) el.innerText = labels[val] || `${val} pts`;
}

function atualizarCalculosSTL() {
  const scaleDenom = parseFloat(document.getElementById('stl-scale-input').value) || 50000;
  const verticalExag = parseFloat(document.getElementById('stl-exag-range').value) || 2.0;
  const rawBase = parseFloat(document.getElementById('stl-base-input').value);
  const baseMm = isNaN(rawBase) ? 0.0 : Math.max(0.0, rawBase);

  document.getElementById('stl-exag-val').innerText = `${verticalExag.toFixed(1)}x`;

  // Cálculos em milímetros
  const widthMm = (currentStlRealWidthM * 1000.0) / scaleDenom;
  const lengthMm = (currentStlRealHeightM * 1000.0) / scaleDenom;
  const reliefMm = ((currentStlDeltaZM * 1000.0) / scaleDenom) * verticalExag;
  const totalZMm = baseMm + reliefMm;

  // Atualiza interface
  document.getElementById('stl-calc-width').innerText = `${widthMm.toFixed(1)} mm`;
  document.getElementById('stl-calc-length').innerText = `${lengthMm.toFixed(1)} mm`;
  document.getElementById('stl-calc-relief').innerText = `${reliefMm.toFixed(1)} mm`;
  document.getElementById('stl-calc-base').innerText = `${baseMm.toFixed(1)} mm`;
  document.getElementById('stl-calc-total-z').innerText = `${totalZMm.toFixed(1)} mm`;

  document.getElementById('stl-real-km').innerText = `${(currentStlRealWidthM / 1000).toFixed(2)} km × ${(currentStlRealHeightM / 1000).toFixed(2)} km`;
  document.getElementById('stl-real-dz').innerText = `${currentStlDeltaZM.toFixed(0)} m`;
}

async function executarExportacaoSTL() {
  if (!currentStlLayer) return;

  const btn = document.getElementById('btn-export-stl-exec');
  const statusMsg = document.getElementById('stl-status-msg');
  const scaleDenom = parseFloat(document.getElementById('stl-scale-input').value) || 50000;
  const verticalExag = parseFloat(document.getElementById('stl-exag-range').value) || 2.0;
  const rawBase = parseFloat(document.getElementById('stl-base-input').value);
  const baseMm = isNaN(rawBase) ? 0.0 : Math.max(0.0, rawBase);
  const rawSmooth = parseFloat(document.getElementById('stl-smooth-range').value);
  const smoothingLevel = isNaN(rawSmooth) ? 0.0 : Math.max(0.0, rawSmooth);
  const maxGrid = parseInt(document.getElementById('stl-res-select').value) || 1000;

  btn.disabled = true;
  btn.innerHTML = `<span style="display:inline-block; animation:spin 1s infinite linear;">⚙️</span> Gerando STL...`;
  statusMsg.innerHTML = `<span style="color: #d84315; font-weight: bold;">Gerando malha sólida manifold e calculando normais...</span>`;
  simularProgressoPasso("Construindo malha 3D sólida manifold (STL)...", 3000);
  showToast("Processando modelo STL para impressão 3D...");

  try {
    const payload = {
      layer_id: currentStlLayer.id,
      scale_denom: scaleDenom,
      vertical_exag: verticalExag,
      base_thickness_mm: baseMm,
      smoothing_level: smoothingLevel,
      max_grid: maxGrid
    };

    const resp = await fetch('/api/export-stl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await resp.json();
    if (!resp.ok || data.error) {
      throw new Error(data.error || "Falha ao gerar arquivo STL.");
    }

    // Dispara o download nativo do arquivo STL
    const a = document.createElement('a');
    a.href = data.download_url;
    a.download = data.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    statusMsg.innerHTML = `<span style="color: #2e7d32; font-weight: bold;">✓ Sucesso! ${data.metadata.triangles_count.toLocaleString()} triângulos (${data.metadata.file_size_kb} KB).</span>`;
    showToast(`Modelo STL baixado: ${data.filename}`);
    finalizarProgresso(`Pronto. STL gerado: ${data.metadata.width_mm}mm × ${data.metadata.length_mm}mm × ${data.metadata.total_height_mm}mm`);

  } catch (err) {
    console.error(err);
    alert(`Erro ao exportar STL: ${err.message}`);
    statusMsg.innerHTML = `<span style="color: #c62828;">Erro: ${err.message}</span>`;
    cancelarProgresso("Erro ao gerar STL.");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `📥 Gerar e Baixar .STL`;
  }
}

/**
 * ==============================================================================
 * 15. Integração com Malhas Vetoriais Oficiais do IBGE
 * ==============================================================================
 */

/**
 * Carrega a lista oficial de UFs para o seletor do modal
 */
async function carregarListaUFsIBGE() {
  const select = document.getElementById('ibge-uf-select');
  if (!select) return;

  try {
    const resp = await fetch('/api/ibge/ufs');
    const data = await resp.json();
    const ufsList = Array.isArray(data) ? data : (data.ufs || []);
    if (ufsList.length > 0) {
      select.innerHTML = '';
      ufsList.forEach(uf => {
        const opt = document.createElement('option');
        opt.value = uf.sigla;
        opt.innerText = `${uf.nome} (${uf.sigla})`;
        if (uf.sigla === 'SP') opt.selected = true;
        select.appendChild(opt);
      });
    }
  } catch (e) {
    console.warn("Não foi possível carregar a lista de UFs do IBGE:", e);
  }
}

function abrirModalIBGE() {
  fecharTodosMenus();
  document.getElementById('modal-ibge').classList.add('show');
}

function fecharModalIBGE() {
  document.getElementById('modal-ibge').classList.remove('show');
}

function abrirModalSelecaoMunicipios() {
  fecharTodosMenus();
  abrirModalIBGE();
  const select = document.getElementById('ibge-mesh-type-select');
  if (select) {
    select.value = 'municipios';
    onIbgeMeshTypeChange('municipios');
  }
}

function abrirModalSelecaoMesorregioes() {
  fecharTodosMenus();
  abrirModalIBGE();
  const select = document.getElementById('ibge-mesh-type-select');
  if (select) {
    select.value = 'mesorregioes';
    onIbgeMeshTypeChange('mesorregioes');
  }
}

function onIbgeMeshTypeChange(val) {
  const ufGroup = document.getElementById('ibge-uf-selector-group');
  if (ufGroup) {
    ufGroup.style.display = (val === 'municipios' || val === 'mesorregioes') ? 'block' : 'none';
  }
}

async function adicionarMalhaSelecionadaIBGE() {
  const type = document.getElementById('ibge-mesh-type-select').value;
  const uf = document.getElementById('ibge-uf-select').value;
  const needsUf = (type === 'municipios' || type === 'mesorregioes');
  await adicionarMalhaIBGE(type, needsUf ? uf : '');
}

/**
 * Solicita e adiciona uma malha oficial do IBGE como camada vetorial
 */
async function adicionarMalhaIBGE(type, uf) {
  fecharTodosMenus();
  const loadingStatus = document.getElementById('ibge-loading-status');
  const btnAdd = document.getElementById('btn-add-ibge');

  if (loadingStatus) loadingStatus.style.display = 'block';
  if (btnAdd) {
    btnAdd.disabled = true;
    btnAdd.innerHTML = `<span style="display:inline-block; animation:spin 1s infinite linear;">⚙️</span> Carregando...`;
  }

  const ufParam = uf ? `&uf=${encodeURIComponent(uf)}` : '';
  const url = `/api/ibge/mesh?type=${encodeURIComponent(type)}${ufParam}`;

  simularProgressoPasso(`Carregando malha do IBGE (${type.toUpperCase()}${uf ? ' - ' + uf : ''})...`, 2500);
  showToast(`Baixando malha oficial do IBGE...`);

  try {
    const resp = await fetch(url);
    const data = await resp.json();

    if (!resp.ok || data.error) {
      throw new Error(data.error || "Erro ao obter malha do IBGE.");
    }

    // Adiciona ao mapa Leaflet e ao painel de camadas
    adicionarCamadaVetorial(data.layer);
    fecharModalIBGE();

    showToast(`Camada "${data.layer.name}" adicionada com ${data.layer.feature_count} feições!`);
    finalizarProgresso(`Pronto. Camada ${data.layer.name} carregada (${data.layer.feature_count} feições).`);

  } catch (err) {
    console.error(err);
    alert(`Erro ao carregar malha do IBGE: ${err.message}`);
    cancelarProgresso("Erro ao carregar dados do IBGE.");
  } finally {
    if (loadingStatus) loadingStatus.style.display = 'none';
    if (btnAdd) {
      btnAdd.disabled = false;
      btnAdd.innerHTML = `➕ Adicionar ao Projeto`;
    }
  }
}

/**
 * Adiciona camada vetorial Leaflet e registra no painel de camadas
 */
function adicionarCamadaVetorial(layer) {
  // Paletas de cores inteligentes por tipo de malha
  const meshColors = {
    brasil: { stroke: '#1a237e', fill: '#3f51b5', opacity: 0.12 },
    regioes: { stroke: '#bf360c', fill: '#ff5722', opacity: 0.15 },
    estados: { stroke: '#0d652d', fill: '#4caf50', opacity: 0.15 },
    mesorregioes: { stroke: '#6a1b9a', fill: '#ab47bc', opacity: 0.16 },
    mesorregioes_brasil: { stroke: '#6a1b9a', fill: '#ab47bc', opacity: 0.16 },
    municipios: { stroke: '#006064', fill: '#00bcd4', opacity: 0.18 }
  };

  const defaultPalette = meshColors[layer.mesh_type] || { stroke: '#0d652d', fill: '#4caf50', opacity: 0.15 };
  const strokeColor = document.getElementById('ibge-stroke-color')?.value || defaultPalette.stroke;
  const fillColor = document.getElementById('ibge-fill-color')?.value || defaultPalette.fill;
  const fillOpacity = parseFloat(document.getElementById('ibge-opacity-range')?.value) || defaultPalette.opacity;

  const defaultStyle = {
    color: strokeColor,
    weight: 1.5,
    opacity: 0.9,
    fillColor: fillColor,
    fillOpacity: fillOpacity
  };

  const featureLayers = [];

  const geoJsonLayer = L.geoJSON(layer.geojson, {
    style: function(feature) {
      return Object.assign({}, defaultStyle);
    },
    onEachFeature: function(feature, fLayer) {
      featureLayers.push(fLayer);

      // Popup de atributos estilo QGIS com botão para recorte SRTM
      const props = feature.properties || {};
      const title = props.NM_MUN || props.NM_MESO || props.NM_UF || props.NM_REGIAO || props.NOME || 'Feição IBGE';
      let html = `<div style="font-family:'Segoe UI',sans-serif; font-size:11px; min-width:200px; max-width:290px;">`;
      html += `<div style="font-weight:bold; color:#0d652d; border-bottom:1px solid #c2e0c6; padding-bottom:3px; margin-bottom:5px; font-size:12px;">🏛️ ${title}</div>`;
      html += `<table style="width:100%; border-collapse:collapse; font-size:11px;">`;
      for (const [k, v] of Object.entries(props)) {
        if (k.startsWith('_')) continue;
        html += `<tr style="border-bottom:1px solid #f0f0f0;"><td style="color:#666; padding:2px 4px 2px 0; font-weight:600;">${k}:</td><td style="color:#222; padding:2px 0;">${v !== null && v !== undefined ? v : '-'}</td></tr>`;
      }
      html += `</table>`;
      html += `<div style="margin-top:8px; padding-top:6px; border-top:1px solid #e0e0e0;">`;
      html += `<button class="qgis-btn primary" onclick="solicitarSRTMFeicaoSelecionada()" style="width:100%; display:flex; align-items:center; justify-content:center; gap:5px; background:linear-gradient(180deg, #1976d2 0%, #1565c0 100%); color:#fff; font-weight:600; font-size:11px; padding:5px 8px; cursor:pointer; border-radius:3px; border:1px solid #0d47a1;">`;
      html += `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>`;
      html += `<span>⛰️ Extrair e Recortar SRTM 30m</span>`;
      html += `</button>`;
      html += `</div></div>`;
      fLayer.bindPopup(html);

      // Eventos de hover interativo
      fLayer.on('mouseover', function(e) {
        if (fLayer !== highlightedMapFeatureLayer) {
          fLayer.setStyle({
            weight: 2.5,
            color: '#1a56a6',
            fillOpacity: Math.min(fillOpacity + 0.25, 0.6)
          });
        }
        if (title) setStatusMsg(`IBGE: ${title}`);
      });

      fLayer.on('mouseout', function(e) {
        if (fLayer !== highlightedMapFeatureLayer) {
          geoJsonLayer.resetStyle(fLayer);
        }
      });

      fLayer.on('click', function(e) {
        selecionarCamadaItem(layer.id);
        selecionarFeicaoVetorial(feature, fLayer, layer.id, title);
      });
    }
  }).addTo(map);

  // Registra no estado global
  layersRegistry[layer.id] = {
    type: 'vector',
    metadata: layer,
    overlay: geoJsonLayer,
    layerGroup: geoJsonLayer,
    featureLayers: featureLayers,
    opacity: fillOpacity,
    strokeColor: strokeColor,
    fillColor: fillColor,
    geojson: layer.geojson
  };
  activeLayerId = layer.id;

  // Zoom no mapa para a extensão do vetor
  if (geoJsonLayer.getBounds().isValid()) {
    map.fitBounds(geoJsonLayer.getBounds(), { padding: [25, 25] });
  }

  // Renderiza item na árvore de camadas
  renderizarItemCamadaVetorial(layer, strokeColor, fillColor);
}

/**
 * Renderiza o elemento HTML da camada vetorial no painel "Camadas"
 */
function renderizarItemCamadaVetorial(layer, strokeColor, fillColor) {
  const container = document.getElementById('layers-tree-container');

  // Remove seleção ativa anterior
  document.querySelectorAll('.layer-item').forEach(el => el.classList.remove('active'));

  const item = document.createElement('div');
  item.className = 'layer-item active';
  item.id = `layer-item-${layer.id}`;
  item.dataset.id = layer.id;

  item.innerHTML = `
    <div class="layer-header-row">
      <input type="checkbox" class="layer-checkbox" id="check-${layer.id}" checked>
      <div class="layer-type-icon" title="Camada Vetorial Poligonal QGIS">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <polygon points="4,4 20,6 18,18 6,19" fill="${fillColor}" fill-opacity="0.45" stroke="${strokeColor}" stroke-width="2"/>
          <circle cx="4" cy="4" r="2" fill="#fff" stroke="${strokeColor}" stroke-width="1.2"/>
          <circle cx="20" cy="6" r="2" fill="#fff" stroke="${strokeColor}" stroke-width="1.2"/>
          <circle cx="18" cy="18" r="2" fill="#fff" stroke="${strokeColor}" stroke-width="1.2"/>
          <circle cx="6" cy="19" r="2" fill="#fff" stroke="${strokeColor}" stroke-width="1.2"/>
        </svg>
      </div>
      <span class="layer-name" title="${layer.name} (${layer.feature_count} feições)">${layer.name}</span>
      <span class="layer-quick-download" style="color:#0d652d; border-color:#c2e0c6; background:#edf7ed;" title="Exportar (.gpkg / .kml)" onclick="event.stopPropagation(); abrirModalExportVector('${layer.id}')">
        📦 Exportar
      </span>
    </div>
    <div class="layer-legend">
      <div style="font-size: 10px; color: #555; display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 1px 2px;">
        <span style="display:flex; align-items:center; gap:4px;">
          <span style="display:inline-block; width:10px; height:10px; background:${fillColor}; border:1px solid ${strokeColor}; border-radius:2px;"></span>
          Polígonos OGC
        </span>
        <span style="font-weight: 600; color: #0d652d;">${layer.feature_count} feições</span>
      </div>
    </div>
  `;

  layersRegistry[layer.id].domElement = item;

  // Clique simples: define como camada ativa
  item.addEventListener('click', (e) => {
    document.querySelectorAll('.layer-item').forEach(el => el.classList.remove('active'));
    item.classList.add('active');
    activeLayerId = layer.id;
  });

  // Checkbox de visibilidade
  const check = item.querySelector(`#check-${layer.id}`);
  check.addEventListener('change', (e) => {
    e.stopPropagation();
    toggleLayerVisibility(layer.id, check.checked);
  });

  // Clique com botão direito: menu de contexto especializado
  item.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    e.stopPropagation();

    document.querySelectorAll('.layer-item').forEach(el => el.classList.remove('active'));
    item.classList.add('active');
    activeLayerId = layer.id;

    abrirContextMenu(e.clientX, e.clientY, layer.id);
  });

  // Insere no topo da lista (acima do basemap)
  const basemapItem = document.getElementById('layer-item-basemap');
  container.insertBefore(item, basemapItem);
}

function selecionarCamadaItem(layerId) {
  document.querySelectorAll('.layer-item').forEach(el => el.classList.remove('active'));
  const el = document.getElementById(`layer-item-${layerId}`);
  if (el) el.classList.add('active');
  activeLayerId = layerId;
}

/**
 * ==============================================================================
 * 16. Modal de Exportação Vetorial Dedicada (.gpkg, .kml com definição de SRC)
 * ==============================================================================
 */

let currentExportVectorLayerId = null;

function abrirModalExportVector(layerId) {
  const targetId = layerId || activeLayerId;
  if (!targetId || !layersRegistry[targetId]) {
    alert("Selecione uma camada vetorial para exportar.");
    return;
  }

  const reg = layersRegistry[targetId];
  if (reg.type !== 'vector') {
    alert("A exportação vetorial (.gpkg / .kml) é destinada a camadas vetoriais. Para rasters, utilize 'Salvar Como GeoTIFF'.");
    return;
  }

  currentExportVectorLayerId = targetId;

  document.getElementById('export-vec-layer-name').innerText = reg.metadata.name;

  // Nome sugerido padrão sem espaços nem caracteres especiais
  const safeName = reg.metadata.name
    .normalize('NFD').replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9_-]/g, "_")
    .replace(/__+/g, "_")
    .toLowerCase();
  document.getElementById('export-vec-filename').value = safeName;

  document.getElementById('export-vec-format').value = 'gpkg';
  onVectorFormatChange('gpkg');
  document.getElementById('export-vec-crs').value = 'EPSG:4674';

  const statusEl = document.getElementById('export-vec-status');
  if (statusEl) {
    statusEl.style.display = 'none';
    statusEl.innerText = '';
  }

  fecharContextMenu();
  document.getElementById('modal-export-vector').classList.add('show');
}

function fecharModalExportVector() {
  document.getElementById('modal-export-vector').classList.remove('show');
  currentExportVectorLayerId = null;
}

function contextOpenExportVectorModal() {
  fecharContextMenu();
  if (activeLayerId) {
    abrirModalExportVector(activeLayerId);
  }
}

function onVectorFormatChange(fmt) {
  const descEl = document.getElementById('export-vec-format-desc');
  if (!descEl) return;

  const descs = {
    gpkg: "GeoPackage OGC (.gpkg) - Padrão moderno em SQLite aberto. Preserva todas as geometrias, atributos alfanuméricos e CRS exato.",
    kml: "Keyhole Markup Language (.kml) - Compatível com Google Earth, QGIS e plataformas web com ExtendedData de atributos.",
    geojson: "GeoJSON (.geojson) - Formato de texto aberto padrão da IETF amplamente suportado na web e no QGIS.",
    shp: "ESRI Shapefile compactado (.zip) contendo os arquivos .shp, .shx, .dbf e .prj."
  };
  descEl.innerText = descs[fmt] || "";
}

async function executarExportacaoVetorial() {
  if (!currentExportVectorLayerId || !layersRegistry[currentExportVectorLayerId]) {
    alert("Nenhuma camada vetorial selecionada.");
    return;
  }

  const reg = layersRegistry[currentExportVectorLayerId];
  const btn = document.getElementById('btn-export-vec-exec');
  const statusEl = document.getElementById('export-vec-status');

  const format = document.getElementById('export-vec-format').value;
  const targetCrs = document.getElementById('export-vec-crs').value;
  let filename = document.getElementById('export-vec-filename').value.trim();
  if (!filename) {
    filename = reg.metadata.name.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
  }

  btn.disabled = true;
  btn.innerHTML = `<span style="display:inline-block; animation:spin 1s infinite linear;">⚙️</span> Exportando...`;
  if (statusEl) {
    statusEl.style.display = 'block';
    statusEl.style.color = '#1a56a6';
    statusEl.innerText = `Processando geometrias e reprojetando para ${targetCrs}...`;
  }
  simularProgressoPasso(`Exportando vetor para ${format.toUpperCase()} (${targetCrs})...`, 2500);
  showToast(`Exportando para ${format.toUpperCase()} (${targetCrs})...`);

  try {
    // Extrai cópia limpa e estrita do GeoJSON sem nenhuma referência circular
    const cleanFeatures = (reg.geojson.features || []).map(f => ({
      type: "Feature",
      geometry: f.geometry,
      properties: Object.fromEntries(
        Object.entries(f.properties || {}).filter(([k]) => !k.startsWith('_'))
      )
    }));

    const cleanGeoJson = {
      type: "FeatureCollection",
      features: cleanFeatures
    };

    const payload = {
      layer_id: currentExportVectorLayerId,
      format: format,
      target_crs: targetCrs,
      geojson: cleanGeoJson,
      layer_name: filename
    };

    const resp = await fetch('/api/ibge/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await resp.json();
    if (!resp.ok || data.error) {
      throw new Error(data.error || "Falha ao exportar camada vetorial.");
    }

    // Dispara o download nativo no navegador
    const a = document.createElement('a');
    a.href = data.download_url;
    a.download = data.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    showToast(`Arquivo vetorial baixado: ${data.filename}`);
    finalizarProgresso(`Pronto. Arquivo ${data.filename} exportado (${data.feature_count} feições, SRC ${targetCrs}).`);

    fecharModalExportVector();

  } catch (err) {
    console.error(err);
    alert(`Erro na exportação vetorial: ${err.message}`);
    cancelarProgresso("Erro na exportação vetorial.");
    if (statusEl) {
      statusEl.style.color = '#c62828';
      statusEl.innerText = `Erro: ${err.message}`;
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = `📥 Exportar e Baixar`;
  }
}

/**
 * ==============================================================================
 * 17. Visualizador da Tabela de Atributos (Estilo QGIS)
 * ==============================================================================
 */

let currentAttrLayerId = null;
let currentAttrFeatures = [];
let currentAttrColumns = [];
let highlightedMapFeatureLayer = null;

function abrirTabelaAtributos(layerId) {
  const targetId = layerId || activeLayerId;
  if (!targetId || !layersRegistry[targetId]) {
    alert("Selecione uma camada vetorial para abrir a tabela de atributos.");
    return;
  }

  const reg = layersRegistry[targetId];
  if (reg.type !== 'vector') {
    alert("A tabela de atributos está disponível apenas para camadas vetoriais.");
    return;
  }

  currentAttrLayerId = targetId;
  currentAttrFeatures = (reg.geojson && reg.geojson.features) ? reg.geojson.features : [];

  // Configura título e contadores
  document.getElementById('attr-dialog-title').innerText = `Tabela de Atributos - ${reg.metadata.name} (${currentAttrFeatures.length} feições)`;
  document.getElementById('attr-feature-count').innerText = `Total: ${currentAttrFeatures.length} feições`;
  document.getElementById('attr-search-input').value = '';
  document.getElementById('attr-selected-status').innerHTML = 'Nenhuma feição selecionada';

  // Identifica todas as colunas de atributos
  currentAttrColumns = [];
  if (reg.metadata.fields && reg.metadata.fields.length > 0) {
    currentAttrColumns = reg.metadata.fields.filter(f => !f.startsWith('_'));
  } else if (currentAttrFeatures.length > 0) {
    const firstProps = currentAttrFeatures[0].properties || {};
    currentAttrColumns = Object.keys(firstProps).filter(f => !f.startsWith('_'));
  }

  // Renderiza cabeçalho
  const thead = document.getElementById('attr-table-head');
  let theadHtml = `<tr><th style="width: 45px; text-align: center;">#</th>`;
  currentAttrColumns.forEach(col => {
    theadHtml += `<th>${col}</th>`;
  });
  theadHtml += `</tr>`;
  thead.innerHTML = theadHtml;

  // Renderiza corpo da tabela
  const tbody = document.getElementById('attr-table-body');
  let tbodyHtml = '';
  currentAttrFeatures.forEach((feat, idx) => {
    const props = feat.properties || {};
    tbodyHtml += `<tr id="attr-row-${idx}" onclick="selecionarFeicaoTabela(${idx})" title="Clique para aproximar no mapa">`;
    tbodyHtml += `<td class="row-num" style="text-align: center;">${idx + 1}</td>`;
    currentAttrColumns.forEach(col => {
      const val = props[col] !== null && props[col] !== undefined ? props[col] : '';
      tbodyHtml += `<td>${val}</td>`;
    });
    tbodyHtml += `</tr>`;
  });
  tbody.innerHTML = tbodyHtml;

  fecharContextMenu();
  document.getElementById('modal-attributes').classList.add('show');
}

function fecharTabelaAtributos() {
  document.getElementById('modal-attributes').classList.remove('show');

  // Limpa realce do mapa se houver
  if (highlightedMapFeatureLayer && currentAttrLayerId && layersRegistry[currentAttrLayerId]) {
    layersRegistry[currentAttrLayerId].layerGroup.resetStyle(highlightedMapFeatureLayer);
    highlightedMapFeatureLayer = null;
  }
}

function contextOpenAttributeTable() {
  fecharContextMenu();
  if (activeLayerId) {
    abrirTabelaAtributos(activeLayerId);
  }
}

function abrirTabelaAtributosCamadaAtiva() {
  if (activeLayerId && layersRegistry[activeLayerId] && layersRegistry[activeLayerId].type === 'vector') {
    abrirTabelaAtributos(activeLayerId);
  } else {
    // Procura a primeira camada vetorial disponível
    const vecId = Object.keys(layersRegistry).find(id => layersRegistry[id].type === 'vector');
    if (vecId) {
      selecionarCamadaItem(vecId);
      abrirTabelaAtributos(vecId);
    } else {
      showToast("Carregue uma camada oficial do IBGE para visualizar a tabela de atributos.");
      abrirModalIBGE();
    }
  }
}

function filtrarTabelaAtributos(query) {
  const q = (query || '').toLowerCase().trim();
  let visibleCount = 0;

  currentAttrFeatures.forEach((feat, idx) => {
    const row = document.getElementById(`attr-row-${idx}`);
    if (!row) return;

    if (!q) {
      row.style.display = '';
      visibleCount++;
    } else {
      const props = feat.properties || {};
      const match = Object.values(props).some(v => String(v).toLowerCase().includes(q));
      if (match) {
        row.style.display = '';
        visibleCount++;
      } else {
        row.style.display = 'none';
      }
    }
  });

  const countEl = document.getElementById('attr-feature-count');
  if (countEl) {
    countEl.innerText = `${visibleCount} de ${currentAttrFeatures.length} feições`;
  }
}

function selecionarFeicaoTabela(idx) {
  const feat = currentAttrFeatures[idx];
  if (!feat) return;

  // Atualiza classe selecionada na tabela
  document.querySelectorAll('#attr-table-body tr').forEach(r => r.classList.remove('selected'));
  const row = document.getElementById(`attr-row-${idx}`);
  if (row) row.classList.add('selected');

  // Informa na barra de status da tabela
  const props = feat.properties || {};
  const name = props.NM_MUN || props.NM_MESO || props.NM_UF || props.NM_REGIAO || props.NOME || props.codarea || `Linha ${idx + 1}`;
  document.getElementById('attr-selected-status').innerHTML = `Feição selecionada: <strong>${name}</strong> (Linha ${idx + 1})`;

  // Encontra a camada Leaflet correspondente
  const reg = layersRegistry[currentAttrLayerId];
  if (!reg || !reg.layerGroup) return;

  // Reseta realce anterior
  if (highlightedMapFeatureLayer) {
    reg.layerGroup.resetStyle(highlightedMapFeatureLayer);
    highlightedMapFeatureLayer = null;
  }

  let targetLeafletLayer = (reg.featureLayers && reg.featureLayers[idx]) ? reg.featureLayers[idx] : null;
  if (!targetLeafletLayer) {
    reg.layerGroup.eachLayer(l => {
      if (l.feature === feat || (l.feature && l.feature.properties && l.feature.properties.codarea === props.codarea)) {
        targetLeafletLayer = l;
      }
    });
  }

  // Registra globalmente como a feição vetorial selecionada
  selecionarFeicaoVetorial(feat, targetLeafletLayer, currentAttrLayerId, name);

  if (targetLeafletLayer) {
    // Aproxima e centraliza no mapa
    if (targetLeafletLayer.getBounds && targetLeafletLayer.getBounds().isValid()) {
      map.fitBounds(targetLeafletLayer.getBounds(), { padding: [80, 80], maxZoom: 14 });
    }

    // Abre o popup com atributos
    targetLeafletLayer.openPopup();
  }

  setStatusMsg(`Feição selecionada: ${name}`);
}

function exportarTabelaCSV() {
  if (!currentAttrFeatures || currentAttrFeatures.length === 0) {
    alert("Nenhum dado para exportar.");
    return;
  }

  // Gera conteúdo CSV com delimitador vírgula e BOM UTF-8 para Excel
  const headers = ['#', ...currentAttrColumns];
  const rows = [headers.map(h => `"${h}"`).join(',')];

  currentAttrFeatures.forEach((feat, idx) => {
    const rowEl = document.getElementById(`attr-row-${idx}`);
    // Se estiver filtrado (oculto), ignora
    if (rowEl && rowEl.style.display === 'none') return;

    const props = feat.properties || {};
    const rowValues = [idx + 1];
    currentAttrColumns.forEach(col => {
      const val = props[col] !== null && props[col] !== undefined ? String(props[col]).replace(/"/g, '""') : '';
      rowValues.push(`"${val}"`);
    });
    rows.push(rowValues.join(','));
  });

  const csvContent = '\uFEFF' + rows.join('\r\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const reg = layersRegistry[currentAttrLayerId];
  const filename = (reg ? reg.metadata.name.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase() : 'ibge') + '_atributos.csv';
  iniciarProgresso(`Exportando tabela CSV (${filename})...`, 80);

  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  showToast(`Tabela de atributos exportada: ${filename}`);
  finalizarProgresso(`Pronto. Tabela CSV exportada: ${filename}`);
}

/**
 * ==============================================================================
 * 18. Seleção de Feição Vetorial e Recorte Automático de SRTM 30m
 * ==============================================================================
 */

function selecionarFeicaoVetorial(feature, leafletLayer, layerId, customName) {
  if (!feature) return;
  const props = feature.properties || {};
  const name = customName || props.NM_MUN || props.NM_MESO || props.NM_UF || props.NM_REGIAO || props.NOME || props.codarea || 'Feição Selecionada';

  selectedVectorFeature = {
    feature: feature,
    leafletLayer: leafletLayer,
    layerId: layerId,
    name: name,
    geometry: feature.geometry
  };

  // Se a camada Leaflet foi fornecida e difere do realce atual, atualiza o realce
  if (leafletLayer && layersRegistry[layerId]) {
    const reg = layersRegistry[layerId];
    if (highlightedMapFeatureLayer && highlightedMapFeatureLayer !== leafletLayer) {
      if (reg.layerGroup) reg.layerGroup.resetStyle(highlightedMapFeatureLayer);
    }
    leafletLayer.setStyle({
      color: '#ff9800',
      weight: 3.5,
      fillColor: '#ffeb3b',
      fillOpacity: 0.55
    });
    leafletLayer.bringToFront();
    highlightedMapFeatureLayer = leafletLayer;
  }

  // Atualiza botão da barra de ferramentas principal
  const btnToolbar = document.getElementById('btn-srtm-feature');
  if (btnToolbar) {
    btnToolbar.title = `Extrair e recortar SRTM 30m para: ${name}`;
    btnToolbar.classList.add('active');
    btnToolbar.style.borderColor = '#1976d2';
    btnToolbar.style.background = '#e3f2fd';
    btnToolbar.style.color = '#0d47a1';
  }

  // Atualiza status da tabela de atributos se visível
  const attrStatus = document.getElementById('attr-selected-status');
  if (attrStatus) {
    attrStatus.innerHTML = `Feição selecionada: <strong>${name}</strong>`;
  }

  setStatusMsg(`Feição selecionada: ${name}`);
}

async function solicitarSRTMFeicaoSelecionada() {
  // Se nenhuma feição foi selecionada explicitamente ainda, tenta pegar da camada ativa
  if (!selectedVectorFeature || !selectedVectorFeature.geometry) {
    if (activeLayerId && layersRegistry[activeLayerId] && layersRegistry[activeLayerId].type === 'vector') {
      const reg = layersRegistry[activeLayerId];
      if (reg.geojson && reg.geojson.features && reg.geojson.features.length === 1) {
        const f0 = reg.geojson.features[0];
        const fName = reg.metadata.name;
        selecionarFeicaoVetorial(f0, (reg.featureLayers && reg.featureLayers[0]) || null, activeLayerId, fName);
      } else {
        alert("Por favor, selecione primeiro uma feição vetorial no mapa (clique sobre um município ou polígono) ou clique em uma linha na Tabela de Atributos.");
        return;
      }
    } else {
      // Procura qualquer camada vetorial carregada
      const vecId = Object.keys(layersRegistry).find(id => layersRegistry[id].type === 'vector');
      if (vecId) {
        selecionarCamadaItem(vecId);
        abrirTabelaAtributos(vecId);
        showToast("Selecione um município ou polígono na tabela ou no mapa.");
        return;
      } else {
        alert("Nenhuma camada vetorial ativa. Adicione uma malha oficial do IBGE pelo menu 'IBGE' ou botão 'Malhas IBGE'.");
        abrirModalIBGE();
        return;
      }
    }
  }

  const feat = selectedVectorFeature;
  const colormap = document.getElementById('select-colormap').value;
  const hillshade = document.getElementById('check-hillshade').checked;
  const btn = document.getElementById('btn-srtm-feature');
  const btnAttr = document.getElementById('btn-attr-srtm');
  const oldBtnHtml = btn ? btn.innerHTML : '';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span style="display:inline-block; animation:spin 1s infinite linear;">⚙️</span> Recortando...`;
  }
  if (btnAttr) {
    btnAttr.disabled = true;
    btnAttr.innerHTML = `<span style="display:inline-block; animation:spin 1s infinite linear;">⚙️</span> Recortando...`;
  }

  simularProgressoPasso(`Recortando relevo SRTM para ${feat.name}...`, 4500);
  showToast(`Baixando e recortando relevo para ${feat.name}... Aguarde alguns instantes.`);

  try {
    const safeName = feat.name.replace(/[^a-zA-Z0-9_\u00C0-\u017F\s-]/g, '').trim();
    const payload = {
      geometry: feat.geometry,
      feature_name: safeName,
      colormap: colormap,
      hillshade: hillshade
    };

    const resp = await fetch('/api/srtm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await resp.json();
    if (!resp.ok || data.error) {
      throw new Error(data.error || "Erro ao processar SRTM da feição.");
    }

    adicionarCamadaRaster(data.layer);
    const resInfo = (data.layer.dimensions && data.layer.dimensions.resolution_label) ? ` [${data.layer.dimensions.resolution_label}]` : '';
    showToast(`SRTM de "${data.layer.name}"${resInfo} gerado e recortado com sucesso!`);
    finalizarProgresso(`Pronto. Relevo de ${feat.name} recortado (${data.layer.stats.min}m a ${data.layer.stats.max}m, resolução: ${data.layer.dimensions.approx_pixel_size_m || 30.87}m).`);

    // Fecha popup no mapa
    if (map) map.closePopup();

  } catch (err) {
    console.error(err);
    alert(`Erro ao baixar/recortar SRTM 30m para a feição selecionada:\n${err.message}`);
    cancelarProgresso("Erro no recorte SRTM.");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = oldBtnHtml;
    }
    if (btnAttr) {
      btnAttr.disabled = false;
      btnAttr.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#0d47a1" stroke-width="2.2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg><span>⛰️ Extrair SRTM</span>`;
    }
  }
}

function contextSRTMFromFeature() {
  fecharContextMenu();
  if (selectedVectorFeature) {
    solicitarSRTMFeicaoSelecionada();
  } else if (activeLayerId && layersRegistry[activeLayerId] && layersRegistry[activeLayerId].type === 'vector') {
    const reg = layersRegistry[activeLayerId];
    if (reg.geojson && reg.geojson.features && reg.geojson.features.length === 1) {
      const f0 = reg.geojson.features[0];
      const fName = reg.metadata.name;
      selecionarFeicaoVetorial(f0, (reg.featureLayers && reg.featureLayers[0]) || null, activeLayerId, fName);
      solicitarSRTMFeicaoSelecionada();
    } else {
      alert("Por favor, selecione uma feição no mapa ou abra a Tabela de Atributos para escolher o município ou polígono a ser recortado.");
      abrirTabelaAtributos(activeLayerId);
    }
  } else {
    alert("Nenhuma camada vetorial selecionada.");
  }
}

/**
 * ==============================================================================
 * 18. Sistema de Janelas Popups Arrastáveis Estilo QGIS Desktop
 * ==============================================================================
 */
function initDraggableDialogs() {
  document.querySelectorAll('.qgis-modal-backdrop').forEach(backdrop => {
    const dialog = backdrop.querySelector('.qgis-dialog');
    if (!dialog) return;
    const titlebar = dialog.querySelector('.dialog-titlebar');
    if (!titlebar) return;

    if (titlebar.dataset.draggableInitialized) return;
    titlebar.dataset.draggableInitialized = 'true';

    let isDragging = false;
    let startX = 0, startY = 0;
    let startLeft = 0, startTop = 0;

    titlebar.addEventListener('mousedown', (e) => {
      // Ignora cliques no botão fechar (✕) ou inputs/botões
      if (e.target.closest('button') || e.target.closest('input') || e.target.closest('.dialog-close-btn') || e.target.closest('.dialog-tab')) {
        return;
      }

      isDragging = true;
      titlebar.style.cursor = 'grabbing';

      const rect = dialog.getBoundingClientRect();
      startX = e.clientX;
      startY = e.clientY;
      startLeft = rect.left;
      startTop = rect.top;

      // Coloca a janela arrastada no topo de todas
      document.querySelectorAll('.qgis-modal-backdrop').forEach(b => b.style.zIndex = '10000');
      backdrop.style.zIndex = '10005';

      // Muda para fixed se ainda estiver com margem automática flex
      dialog.style.position = 'fixed';
      dialog.style.left = `${startLeft}px`;
      dialog.style.top = `${startTop}px`;
      dialog.style.margin = '0';
      dialog.style.transform = 'none';

      function onMouseMove(ev) {
        if (!isDragging) return;
        ev.preventDefault();

        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;

        let newLeft = startLeft + dx;
        let newTop = startTop + dy;

        // Mantém a janela dentro dos limites da tela
        const maxLeft = Math.max(0, window.innerWidth - dialog.offsetWidth);
        const maxTop = Math.max(0, window.innerHeight - dialog.offsetHeight);

        newLeft = Math.max(0, Math.min(newLeft, maxLeft));
        newTop = Math.max(0, Math.min(newTop, maxTop));

        dialog.style.left = `${newLeft}px`;
        dialog.style.top = `${newTop}px`;
      }

      function onMouseUp() {
        if (!isDragging) return;
        isDragging = false;
        titlebar.style.cursor = 'grab';
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
      }

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });
  });
}
