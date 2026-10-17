import os
import pytest
import ibge_service

@pytest.fixture
def sample_feature_collection():
    """Retorna um FeatureCollection GeoJSON valido com um poligono e atributos."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "codarea": "3122306",
                    "NM_MUN": "Divinópolis",
                    "SIGLA_UF": "MG",
                    "NM_UF": "Minas Gerais"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-44.95, -20.18],
                            [-44.80, -20.18],
                            [-44.80, -20.08],
                            [-44.95, -20.08],
                            [-44.95, -20.18]
                        ]
                    ]
                }
            }
        ]
    }

def test_uf_map_integrity():
    """Valida a integridade da tabela de UFs do IBGE (26 estados + 1 DF = 27 UFs)."""
    assert len(ibge_service.UF_MAP) == 27
    assert len(ibge_service.UF_BY_SIGLA) == 27

    # Verifica estados representativos
    assert ibge_service.UF_BY_SIGLA['MG']['nome'] == 'Minas Gerais'
    assert ibge_service.UF_BY_SIGLA['SP']['nome'] == 'São Paulo'
    assert ibge_service.UF_BY_SIGLA['DF']['nome'] == 'Distrito Federal'
    assert ibge_service.UF_BY_SIGLA['AM']['regiao'] == 'Norte'

def test_export_vector_formats(sample_feature_collection):
    """Testa exportacao vetorial nos formatos GeoPackage, GeoJSON e KML."""
    formats = ['geojson', 'gpkg', 'kml']
    
    for fmt in formats:
        out_path, filename, mimetype = ibge_service.export_vector(
            geojson_data=sample_feature_collection,
            layer_name=f"test_layer_{fmt}",
            format_type=fmt,
            target_crs='EPSG:4674'
        )

        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0
        assert fmt in filename.lower()
        assert mimetype is not None

        # Limpeza do arquivo temporario gerado
        try:
            os.remove(out_path)
        except Exception:
            pass

def test_export_vector_empty_validation():
    """Verifica que exportar colecao vazia lanca ValueError explicito."""
    empty_geojson = {"type": "FeatureCollection", "features": []}
    with pytest.raises(ValueError, match="não contém feições"):
        ibge_service.export_vector(empty_geojson, layer_name="vazia", format_type="gpkg")
