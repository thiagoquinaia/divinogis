import pytest
import numpy as np
import srtm_service

def test_skadi_tile_naming():
    """Testa se o calculo dos nomes de quadrícula SRTM (HGT Skadi) esta rigorosamente correto."""
    # Hemisferio Sul / Oeste (ex: Brasil)
    folder, tile_name = srtm_service.get_skadi_tile_info(-21, -45)
    assert folder == "S21"
    assert tile_name == "S21W045"

    folder, tile_name = srtm_service.get_skadi_tile_info(-1, -70)
    assert folder == "S01"
    assert tile_name == "S01W070"

    # Hemisferio Norte / Leste (ex: Europa / Asia)
    folder, tile_name = srtm_service.get_skadi_tile_info(45, 12)
    assert folder == "N45"
    assert tile_name == "N45E012"

    # Origem 0, 0
    folder, tile_name = srtm_service.get_skadi_tile_info(0, 0)
    assert folder == "N00"
    assert tile_name == "N00E000"

def test_fetch_srtm_dem_validation():
    """Testa validacoes de entrada para rejeitar requisicoes invalidas e prevenir travamentos."""
    # 1. Sem coordenadas
    with pytest.raises(ValueError, match="bounds.*não foram fornecidas"):
        srtm_service.fetch_srtm_dem()

    # 2. Coordenadas invertidas (min >= max)
    with pytest.raises(ValueError, match="min_lat/min_lon devem ser menores"):
        srtm_service.fetch_srtm_dem(min_lat=-10.0, max_lat=-20.0, min_lon=-45.0, max_lon=-40.0)

    # 3. Area excessiva (> 22 graus)
    with pytest.raises(ValueError, match="escala continental"):
        srtm_service.fetch_srtm_dem(min_lat=-30.0, max_lat=0.0, min_lon=-60.0, max_lon=-30.0)

def test_elevation_point_query(sample_dem_geotiff):
    """Testa consulta pontual de altitude em um GeoTIFF valido."""
    layer_id = sample_dem_geotiff['id']
    # Coordenadas no centro do fixture (-20.002, -44.998)
    elev = srtm_service.get_elevation_at_point(layer_id, lat=-20.002, lon=-44.998)
    if elev is not None:
        assert isinstance(elev, (int, float))
        assert elev >= 0.0

    # Ponto completamente fora da area do GeoTIFF deve retornar None
    elev_fora = srtm_service.get_elevation_at_point(layer_id, lat=10.0, lon=10.0)
    assert elev_fora is None
