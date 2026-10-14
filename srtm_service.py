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

def fetch_srtm_dem(min_lat, min_lon, max_lat, max_lon, colormap='terrain', blend_hillshade=True):
    """
    Extracts SRTM 30m for the given bounding box [min_lat, min_lon, max_lat, max_lon].
    Mosaics across tiles if necessary.
    Saves a GeoTIFF in exports/ and generates an RGB PNG overlay for map visualization.
    Returns metadata dict.
    """
    if min_lat >= max_lat or min_lon >= max_lon:
        raise ValueError("Coordenadas inválidas: min_lat/min_lon devem ser menores que max_lat/max_lon.")

    # Guard against excessively large bounding boxes (> 4 degrees)
    delta_lat = max_lat - min_lat
    delta_lon = max_lon - min_lon
    if delta_lat > 4.0 or delta_lon > 4.0:
        raise ValueError("A área selecionada é muito grande para processamento direto (máximo 4° x 4°). Por favor selecione uma área menor.")

    # Target resolution: 1 arcsecond = 1 / 3600 degree
    res = 1.0 / 3600.0

    width = max(1, int(round(delta_lon * 3600.0)))
    height = max(1, int(round(delta_lat * 3600.0)))

    # Output array
    dem_output = np.full((height, width), -32768, dtype=np.int16)

    # Global grid pixel coordinates
    # Grid column: 0 at lon 0, 3600 at lon 1
    # Grid row: 0 at lat 0, -3600 at lat 1 (so northern latitudes have negative global rows)
    grid_min_col = int(round(min_lon * 3600.0))
    grid_max_row = int(round(-max_lat * 3600.0))

    lat_min_floor = int(math.floor(min_lat))
    lat_max_floor = int(math.floor(max_lat))
    lon_min_floor = int(math.floor(min_lon))
    lon_max_floor = int(math.floor(max_lon))

    # Iterate over all intersecting 1x1 degree tiles
    for lat_f in range(lat_min_floor, lat_max_floor + 1):
        for lon_f in range(lon_min_floor, lon_max_floor + 1):
            tile_col_origin = lon_f * 3600
            tile_row_origin = -(lat_f + 1) * 3600

            # Compute intersection between tile and requested extent
            c_start = max(grid_min_col, tile_col_origin)
            c_end = min(grid_min_col + width, tile_col_origin + 3600)

            r_start = max(grid_max_row, tile_row_origin)
            r_end = min(grid_max_row + height, tile_row_origin + 3600)

            if c_start < c_end and r_start < r_end:
                tile_arr = load_or_fetch_tile(lat_f, lon_f)

                out_c1 = c_start - grid_min_col
                out_c2 = c_end - grid_min_col
                out_r1 = r_start - grid_max_row
                out_r2 = r_end - grid_max_row

                tile_c1 = c_start - tile_col_origin
                tile_c2 = c_end - tile_col_origin
                tile_r1 = r_start - tile_row_origin
                tile_r2 = r_end - tile_row_origin

                dem_output[out_r1:out_r2, out_c1:out_c2] = tile_arr[tile_r1:tile_r2, tile_c1:tile_c2]

    # Calculate statistics
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

    # Layer IDs and file paths
    layer_id = f"dem_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    tif_filename = f"{layer_id}.tif"
    png_filename = f"{layer_id}.png"
    tif_path = os.path.join(EXPORTS_DIR, tif_filename)
    png_path = os.path.join(EXPORTS_DIR, png_filename)

    # 1. Write GeoTIFF
    transform = from_origin(min_lon, max_lat, res, res)
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

    # 2. Generate visualization PNG (Hillshade + Colormap)
    generate_dem_preview_png(dem_output, valid_mask, min_elev, max_elev, png_path, colormap, blend_hillshade)

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
            "approx_pixel_size_m": 30.87
        },
        "crs": "EPSG:4326 (WGS 84)",
        "file_size": file_size_bytes,
        "download_url": f"/api/download/{layer_id}",
        "preview_url": f"/api/preview/{layer_id}"
    }

def generate_dem_preview_png(dem_output, valid_mask, min_elev, max_elev, output_path, colormap='terrain', blend_hillshade=True):
    """
    Renders shaded relief RGBA image and saves it to output_path.
    """
    height, width = dem_output.shape
    float_dem = dem_output.astype(np.float32)

    # If all values are the same or flat
    if max_elev <= min_elev:
        max_elev = min_elev + 1

    # Choose colormap
    cmap_obj = getattr(plt.cm, colormap, plt.cm.terrain)

    if blend_hillshade and height > 2 and width > 2 and (max_elev - min_elev > 5):
        ls = LightSource(azdeg=315, altdeg=45)
        # Avoid zero division
        norm_dem = (float_dem - min_elev) / max(1.0, float(max_elev - min_elev))
        norm_dem = np.clip(norm_dem, 0, 1)
        
        try:
            rgba = ls.shade(
                float_dem,
                cmap=cmap_obj,
                blend_mode='overlay',
                vert_exag=1.5,
                dx=30.0,
                dy=30.0
            )
        except Exception:
            # Fallback to direct colormap
            rgba = cmap_obj(norm_dem)
    else:
        norm_dem = (float_dem - min_elev) / max(1.0, float(max_elev - min_elev))
        norm_dem = np.clip(norm_dem, 0, 1)
        rgba = cmap_obj(norm_dem)

    # Convert to 0-255 uint8 RGBA
    img_data = (rgba * 255).astype(np.uint8)

    # Set invalid or nodata pixels to full transparency
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
