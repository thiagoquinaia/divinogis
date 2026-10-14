import os
import io
import gzip
import math
import uuid
import time
import requests
import numpy as np

# Ensure PROJ data directory is set cleanly to avoid GDAL/PROJ version mismatch warnings
try:
    import pyproj
    os.environ['PROJ_LIB'] = pyproj.datadir.get_data_dir()
except Exception:
    pass

import rasterio
from rasterio.transform import from_origin
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, Normalize
from PIL import Image

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'data_cache', 'hgt')
EXPORTS_DIR = os.path.join(os.path.dirname(__file__), 'exports')

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

# AWS Skadi base URL (SRTM 30m global 1-arcsecond dataset)
SKADI_BASE_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/skadi'

def get_skadi_tile_info(lat_floor, lon_floor):
    """
    Returns folder and filename for a 1x1 degree Skadi tile.
    lat_floor: integer floor of latitude (-90 to 89)
    lon_floor: integer floor of longitude (-180 to 179)
    """
    lat_prefix = 'N' if lat_floor >= 0 else 'S'
    lon_prefix = 'E' if lon_floor >= 0 else 'W'
    lat_str = f"{lat_prefix}{abs(lat_floor):02d}"
    lon_str = f"{lon_prefix}{abs(lon_floor):03d}"
    tile_name = f"{lat_str}{lon_str}"
    return lat_str, tile_name

def load_or_fetch_tile(lat_floor, lon_floor):
    """
    Loads a 3601x3601 int16 numpy array for the tile.
    If not cached, downloads it from AWS Skadi.
    If tile does not exist (e.g. open ocean, returns 404), returns array of zeros.
    """
    folder, tile_name = get_skadi_tile_info(lat_floor, lon_floor)
    cached_path = os.path.join(CACHE_DIR, f"{tile_name}.hgt.gz")
    raw_hgt_path = os.path.join(CACHE_DIR, f"{tile_name}.hgt")

    raw_bytes = None

    if os.path.exists(raw_hgt_path):
        with open(raw_hgt_path, 'rb') as f:
            raw_bytes = f.read()
    elif os.path.exists(cached_path):
        with gzip.open(cached_path, 'rb') as f:
            raw_bytes = f.read()
    else:
        url = f"{SKADI_BASE_URL}/{folder}/{tile_name}.hgt.gz"
        try:
            resp = requests.get(url, timeout=25)
            if resp.status_code == 200:
                with open(cached_path, 'wb') as f:
                    f.write(resp.content)
                with gzip.GzipFile(fileobj=io.BytesIO(resp.content)) as gz:
                    raw_bytes = gz.read()
            elif resp.status_code == 404:
                # Open ocean or void tile outside coverage
                return np.zeros((3601, 3601), dtype=np.int16)
            else:
                resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            # If network failed or 404
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
                return np.zeros((3601, 3601), dtype=np.int16)
            raise RuntimeError(f"Erro ao baixar tile {tile_name} ({url}): {str(e)}")

    if raw_bytes is None or len(raw_bytes) != 3601 * 3601 * 2:
        return np.zeros((3601, 3601), dtype=np.int16)

    arr = np.frombuffer(raw_bytes, dtype='>i2').reshape((3601, 3601))
    return arr

def fetch_srtm_dem(min_lat=None, min_lon=None, max_lat=None, max_lon=None, colormap='terrain', blend_hillshade=True, geometry=None, feature_name=None, resolution='auto'):
    """
    Extracts SRTM 30m for the given bounding box or GeoJSON geometry polygon.
    Mosaics across tiles with multi-threaded prefetching.
    Supports large regions (up to 22° x 22°) with intelligent adaptive resolution.
    If geometry is provided, masks pixels outside the polygon to NoData (-32768).
    Saves a GeoTIFF in exports/ and generates an RGB PNG overlay for map visualization.
    Returns metadata dict.
    """
    geom_obj = None
    if geometry is not None:
        try:
            import shapely.geometry
            geom_obj = shapely.geometry.shape(geometry)
            if not geom_obj.is_valid:
                geom_obj = geom_obj.buffer(0)
            g_min_lon, g_min_lat, g_max_lon, g_max_lat = geom_obj.bounds
            min_lat = g_min_lat if min_lat is None else min(min_lat, g_min_lat)
            min_lon = g_min_lon if min_lon is None else min(min_lon, g_min_lon)
            max_lat = g_max_lat if max_lat is None else max(max_lat, g_max_lat)
            max_lon = g_max_lon if max_lon is None else max(max_lon, g_max_lon)
        except Exception as e:
            raise ValueError(f"Geometria inválida da feição: {str(e)}")

    if min_lat is None or min_lon is None or max_lat is None or max_lon is None:
        raise ValueError("Coordenadas delimitadoras (bounds) não foram fornecidas.")

    if min_lat >= max_lat or min_lon >= max_lon:
        raise ValueError("Coordenadas inválidas: min_lat/min_lon devem ser menores que max_lat/max_lon.")

    delta_lat = max_lat - min_lat
    delta_lon = max_lon - min_lon
    max_delta = max(delta_lat, delta_lon)

    # Guarda contra áreas continentais gigantescas (> 22° x 22°, ex: continente inteiro)
    if max_delta > 22.0:
        feat_info = f" ('{feature_name}')" if feature_name else ""
        raise ValueError(
            f"A área selecionada{feat_info} é de escala continental ({delta_lon:.1f}° x {delta_lat:.1f}°, máx. 22.0°). "
            f"Para melhor performance, selecione uma Mesorregião, Estado ou delimite uma Área de Interesse (AOI)."
        )

    # Resolução adaptativa inteligente:
    # - step = 1 (~30m): para áreas até 8.0° x 8.0° (cobre 100% das mesorregiões do Brasil, como Triângulo Mineiro, e estados como SP, PR, SC, RJ, RS, etc.)
    # - step = 2 (~60m): para áreas entre 8.0° e 14.0° (grandes estados como Bahia, Minas Gerais)
    # - step = 3 (~90m): para áreas entre 14.0° e 22.0° (macrorregiões ou múltiplos estados)
    step = 1
    if resolution == '60m' or resolution == 60:
        step = 2
    elif resolution == '90m' or resolution == 90:
        step = 3
    elif resolution == 'auto' or resolution == '30m' or resolution is None:
        if max_delta > 14.0:
            step = 3
        elif max_delta > 8.0:
            step = 2
        else:
            step = 1

    # Resolução angular em graus
    res = (1.0 / 3600.0) * step

    width = max(1, int(round(delta_lon / res)))
    height = max(1, int(round(delta_lat / res)))

    # Output array
    dem_output = np.full((height, width), -32768, dtype=np.int16)

    # Coordenadas globais da grade SRTM 1-arcsec (3600 pixels por grau)
    grid_min_col = int(round(min_lon * 3600.0))
    grid_max_row = int(round(-max_lat * 3600.0))

    lat_min_floor = int(math.floor(min_lat))
    lat_max_floor = int(math.floor(max_lat))
    lon_min_floor = int(math.floor(min_lon))
    lon_max_floor = int(math.floor(max_lon))

    # 1. Identifica quadrículas HGT necessárias e baixa em paralelo com ThreadPoolExecutor
    tiles_to_fetch = []
    for lat_f in range(lat_min_floor, lat_max_floor + 1):
        for lon_f in range(lon_min_floor, lon_max_floor + 1):
            tile_col_origin = lon_f * 3600
            tile_row_origin = -(lat_f + 1) * 3600
            if (tile_col_origin < grid_min_col + width * step and tile_col_origin + 3600 > grid_min_col and
                tile_row_origin < grid_max_row + height * step and tile_row_origin + 3600 > grid_max_row):
                tiles_to_fetch.append((lat_f, lon_f))

    if tiles_to_fetch:
        from concurrent.futures import ThreadPoolExecutor
        num_workers = min(10, len(tiles_to_fetch))
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            list(executor.map(lambda p: load_or_fetch_tile(p[0], p[1]), tiles_to_fetch))

    # 2. Monta o mosaico no dem_output aplicando a amostragem por step
    for lat_f in range(lat_min_floor, lat_max_floor + 1):
        for lon_f in range(lon_min_floor, lon_max_floor + 1):
            tile_col_origin = lon_f * 3600
            tile_row_origin = -(lat_f + 1) * 3600

            c_min = max(0, int(math.ceil((tile_col_origin - grid_min_col) / step)))
            c_max = min(width, int(math.ceil((tile_col_origin + 3600 - grid_min_col) / step)))
            r_min = max(0, int(math.ceil((tile_row_origin - grid_max_row) / step)))
            r_max = min(height, int(math.ceil((tile_row_origin + 3600 - grid_max_row) / step)))

            if c_min < c_max and r_min < r_max:
                tile_arr = load_or_fetch_tile(lat_f, lon_f)

                tile_c_start = (grid_min_col + c_min * step) - tile_col_origin
                tile_c_end = (grid_min_col + (c_max - 1) * step) - tile_col_origin + 1
                tile_r_start = (grid_max_row + r_min * step) - tile_row_origin
                tile_r_end = (grid_max_row + (r_max - 1) * step) - tile_row_origin + 1

                dem_output[r_min:r_max, c_min:c_max] = tile_arr[tile_r_start:tile_r_end:step, tile_c_start:tile_c_end:step]

    transform = from_origin(min_lon, max_lat, res, res)

    # 3. Se houver geometria, aplica máscara poligonal exata
    if geom_obj is not None:
        try:
            import rasterio.features
            # invert=True: True dentro da geometria, False fora
            polygon_mask = rasterio.features.geometry_mask(
                [geom_obj],
                out_shape=(height, width),
                transform=transform,
                invert=True
            )
            dem_output[~polygon_mask] = -32768
        except Exception as e:
            print(f"Aviso ao aplicar máscara vetorial SRTM: {e}")

    # 4. Estatísticas de elevação baseadas nos dados válidos
    valid_mask = (dem_output > -1000) & (dem_output < 9000)
    if np.any(valid_mask):
        valid_elevs = dem_output[valid_mask]
        min_elev = int(np.min(valid_elevs))
        max_elev = int(np.max(valid_elevs))
        mean_elev = round(float(np.mean(valid_elevs)), 1)
    else:
        min_elev = 0
        max_elev = 0
        mean_elev = 0.0

    # Layer IDs e nomes de arquivo
    layer_id = f"dem_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    tif_filename = f"{layer_id}.tif"
    png_filename = f"{layer_id}.png"
    tif_path = os.path.join(EXPORTS_DIR, tif_filename)
    png_path = os.path.join(EXPORTS_DIR, png_filename)

    # 5. Salva GeoTIFF com compressão Deflate
    with rasterio.open(
        tif_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype='int16',
        crs='EPSG:4326',
        transform=transform,
        nodata=-32768,
        compress='deflate',
        predictor=2
    ) as dst:
        dst.write(dem_output, 1)

    file_size_bytes = os.path.getsize(tif_path)

    # 6. Gera imagem de pré-visualização PNG (downsampled se maior que 2400px para fluidez e estabilidade)
    max_preview_dim = 2400
    max_dim = max(height, width)
    if max_dim > max_preview_dim:
        preview_step = int(math.ceil(max_dim / max_preview_dim))
        dem_preview = dem_output[::preview_step, ::preview_step]
        valid_preview = valid_mask[::preview_step, ::preview_step]
    else:
        dem_preview = dem_output
        valid_preview = valid_mask

    generate_dem_preview_png(dem_preview, valid_preview, min_elev, max_elev, png_path, colormap, blend_hillshade)

    approx_m = round(30.87 * step, 1)
    res_label = "30m (Alta Resolução SRTM)" if step == 1 else f"{approx_m}m (Adaptado p/ Grande Escala)"

    return {
        "id": layer_id,
        "filename": tif_filename,
        "preview_filename": png_filename,
        "bounds": {
            "min_lat": min_lat,
            "min_lon": min_lon,
            "max_lat": max_lat,
            "max_lon": max_lon
        },
        "leaflet_bounds": [
            [min_lat, min_lon],
            [max_lat, max_lon]
        ],
        "stats": {
            "min": min_elev,
            "max": max_elev,
            "mean": mean_elev
        },
        "dimensions": {
            "width": width,
            "height": height,
            "pixel_size_deg": res,
            "approx_pixel_size_m": approx_m,
            "step": step,
            "resolution_label": res_label
        },
        "crs": "EPSG:4326 (WGS 84)",
        "file_size": file_size_bytes,
        "download_url": f"/api/download/{layer_id}",
        "preview_url": f"/api/preview/{layer_id}",
        "is_clipped": geom_obj is not None,
        "feature_name": feature_name
    }

def generate_dem_preview_png(dem_output, valid_mask, min_elev, max_elev, output_path, colormap='terrain', blend_hillshade=True):
    """
    Renders shaded relief RGBA image with transparent background outside valid mask.
    """
    height, width = dem_output.shape
    float_dem = dem_output.astype(np.float32)

    # Avoid zero division
    if max_elev <= min_elev:
        max_elev = min_elev + 1

    # Fill invalid/nodata pixels with min_elev for smooth hillshade gradient calculation
    if not np.all(valid_mask):
        float_dem[~valid_mask] = float(min_elev)

    cmap_obj = getattr(plt.cm, colormap, plt.cm.terrain)

    if blend_hillshade and height > 2 and width > 2 and (max_elev - min_elev > 5):
        ls = LightSource(azdeg=315, altdeg=45)
        try:
            rgba = ls.shade(
                float_dem,
                cmap=cmap_obj,
                blend_mode='overlay',
                vert_exag=1.5,
                dx=30.0,
                dy=30.0,
                vmin=float(min_elev),
                vmax=float(max_elev)
            )
        except Exception:
            norm_dem = (float_dem - min_elev) / max(1.0, float(max_elev - min_elev))
            norm_dem = np.clip(norm_dem, 0, 1)
            rgba = cmap_obj(norm_dem)
    else:
        norm_dem = (float_dem - min_elev) / max(1.0, float(max_elev - min_elev))
        norm_dem = np.clip(norm_dem, 0, 1)
        rgba = cmap_obj(norm_dem)

    # Convert to 0-255 uint8 RGBA
    img_data = (rgba * 255).astype(np.uint8)

    # Set invalid or nodata pixels outside cutline to 100% transparency
    if not np.all(valid_mask):
        img_data[~valid_mask, 3] = 0

    img = Image.fromarray(img_data, mode='RGBA')
    img.save(output_path, format='PNG')

def get_elevation_at_point(layer_id, lat, lon):
    """
    Reads elevation value from the exported GeoTIFF at the given lat/lon.
    """
    tif_path = os.path.join(EXPORTS_DIR, f"{layer_id}.tif")
    if not os.path.exists(tif_path):
        return None

    try:
        with rasterio.open(tif_path) as src:
            py, px = src.index(lon, lat)
            if 0 <= py < src.height and 0 <= px < src.width:
                val = src.read(1, window=((py, py + 1), (px, px + 1)))[0, 0]
                if val == src.nodata:
                    return None
                return float(val)
    except Exception:
        return None
    return None
