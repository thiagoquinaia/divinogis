import os
import pytest
import numpy as np
import rasterio
from rasterio.transform import from_origin
from app import app as flask_app

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'exports')

@pytest.fixture
def client():
    """Fixture para o cliente de testes da API Flask."""
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as test_client:
        yield test_client

@pytest.fixture
def sample_dem_geotiff():
    """
    Cria um GeoTIFF sintetico pequeno (20x20) para testes de STL e raster,
    contendo relevo positivo e uma regiao com NoData (-32768) simulando
    um recorte por feicao/poligono.
    """
    tif_id = "test_synthetic_fixture"
    tif_path = os.path.join(EXPORTS_DIR, f"{tif_id}.tif")
    
    ny, nx = 20, 20
    # Cria uma cupula de elevacao (ex: 800m a 1400m)
    y_coords, x_coords = np.mgrid[0:ny, 0:nx]
    data = 800.0 + 600.0 * np.sin(np.pi * x_coords / nx) * np.sin(np.pi * y_coords / ny)
    data = data.astype(np.float32)

    # Simula recorte de poligono: cantos marcados como NoData
    nodata_val = -32768.0
    data[0:4, 0:4] = nodata_val
    data[16:20, 16:20] = nodata_val

    transform = from_origin(west=-45.0, north=-20.0, xsize=0.000277, ysize=0.000277)
    
    with rasterio.open(
        tif_path,
        'w',
        driver='GTiff',
        height=ny,
        width=nx,
        count=1,
        dtype=data.dtype,
        crs='EPSG:4326',
        transform=transform,
        nodata=nodata_val
    ) as dst:
        dst.write(data, 1)

    yield {
        'id': tif_id,
        'path': tif_path,
        'width': nx,
        'height': ny,
        'min_elev': 800.0,
        'max_elev': float(np.max(data[data != nodata_val])),
        'nodata': nodata_val
    }

    # Limpeza apos o teste
    for ext in ('.tif', '.png', '.stl'):
        fpath = os.path.join(EXPORTS_DIR, f"{tif_id}{ext}")
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass
