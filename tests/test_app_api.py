import os
import json
import pytest

def test_index_route(client):
    """Testa se a pagina principal do DivinoGIS carrega com sucesso."""
    resp = client.get('/')
    assert resp.status_code == 200
    assert b"DivinoGIS" in resp.data

def test_ibge_ufs_endpoint(client):
    """Testa endpoint que lista todas as UFs brasileiras."""
    resp = client.get('/api/ibge/ufs')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert isinstance(data, list)
    assert len(data) == 27
    # Verifica presenca de siglas essenciais
    siglas = [item['sigla'] for item in data]
    assert 'MG' in siglas
    assert 'SP' in siglas
    assert 'DF' in siglas

def test_export_stl_endpoint_not_found(client):
    """Verifica erro 404 ao tentar exportar STL de camada inexistente."""
    resp = client.post('/api/export-stl', json={'layer_id': 'camada_fantasma_123'})
    assert resp.status_code == 404

def test_export_stl_endpoint_success(client, sample_dem_geotiff):
    """Testa fluxo completo de exportacao STL via API com base 0.0 mm e alta resolucao."""
    layer_id = sample_dem_geotiff['id']
    payload = {
        'layer_id': layer_id,
        'scale_denom': 25000,
        'vertical_exag': 2.0,
        'base_thickness_mm': 0.0,
        'smoothing_level': 0.0,
        'max_grid': 60
    }
    resp = client.post('/api/export-stl', json=payload)
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['success'] is True
    assert 'filename' in data
    assert 'download_url' in data
    assert data['metadata']['base_thickness_mm'] == 0.0

    # Testa download do arquivo STL gerado
    download_url = data['download_url']
    dl_resp = client.get(download_url)
    assert dl_resp.status_code == 200
    assert dl_resp.mimetype == 'application/sla'
    assert len(dl_resp.data) > 84

def test_elevation_grid_endpoint(client, sample_dem_geotiff):
    """Testa extracao da grade de elevacao simplificada para o visualizador 3D do navegador."""
    layer_id = sample_dem_geotiff['id']
    resp = client.get(f'/api/elevation-grid/{layer_id}')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert 'nx' in data
    assert 'ny' in data
    assert 'elevations' in data
    assert len(data['elevations']) == data['nx'] * data['ny']

def test_preview_not_found(client):
    """Verifica que requisitar preview inexistente retorna 404."""
    resp = client.get('/api/preview/nao_existe.png')
    assert resp.status_code == 404
