import os
import io
import math
import numpy as np
import rasterio
from rasterio.enums import Resampling
from scipy.ndimage import gaussian_filter

def calculate_real_world_dimensions(bounds):
    """
    Calculates width (X) and height (Y) in meters for a bounding box in WGS84.
    bounds: dict or object with min_lat, max_lat, min_lon, max_lon
    """
    min_lat = bounds['min_lat'] if isinstance(bounds, dict) else bounds.min_lat
    max_lat = bounds['max_lat'] if isinstance(bounds, dict) else bounds.max_lat
    min_lon = bounds['min_lon'] if isinstance(bounds, dict) else bounds.min_lon
    max_lon = bounds['max_lon'] if isinstance(bounds, dict) else bounds.max_lon

    mid_lat = (min_lat + max_lat) / 2.0
    lat_rad = math.radians(mid_lat)

    # Earth radius ~ 6,371,000 meters
    m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * lat_rad) + 1.175 * math.cos(4 * lat_rad)
    m_per_deg_lon = 111412.84 * math.cos(lat_rad) - 93.5 * math.cos(3 * lat_rad)

    height_m = (max_lat - min_lat) * m_per_deg_lat
    width_m = (max_lon - min_lon) * m_per_deg_lon

    return max(1.0, width_m), max(1.0, height_m)

def build_solid_stl_mesh(xs, ys, zs, valid_mask=None, base_z=0.0):
    """
    Constructs a 100% watertight, closed 2-manifold STL triangular solid mesh.
    Supports both rectangular bounding boxes and irregular polygon cutlines:
    - If valid_mask is provided, only quads with valid elevation data are triangulated.
    - Vertical boundary walls are dynamically generated along the perimeter of the valid
      polygon (wherever valid terrain borders NoData or the raster bounds), dropping down to base_z.
    - If valid_mask is None or fully True, generates the standard 4 outer walls.
    """
    R, C = zs.shape
    grid_x, grid_y = np.meshgrid(xs, ys)

    if valid_mask is None:
        quad_valid = np.ones((R - 1, C - 1), dtype=bool)
    else:
        quad_valid = (
            valid_mask[:-1, :-1] &
            valid_mask[:-1, 1:] &
            valid_mask[1:, :-1] &
            valid_mask[1:, 1:]
        )

    r_idx, c_idx = np.where(quad_valid)
    if len(r_idx) == 0:
        raise ValueError("Nenhum dado ou feição topográfica válida para gerar a malha STL.")

    # 1. Top surface vertices
    v00 = np.stack([grid_x[r_idx, c_idx], grid_y[r_idx, c_idx], zs[r_idx, c_idx]], axis=-1)
    v01 = np.stack([grid_x[r_idx, c_idx+1], grid_y[r_idx, c_idx+1], zs[r_idx, c_idx+1]], axis=-1)
    v10 = np.stack([grid_x[r_idx+1, c_idx], grid_y[r_idx+1, c_idx], zs[r_idx+1, c_idx]], axis=-1)
    v11 = np.stack([grid_x[r_idx+1, c_idx+1], grid_y[r_idx+1, c_idx+1], zs[r_idx+1, c_idx+1]], axis=-1)

    top_t1 = np.stack([v00, v10, v01], axis=1)
    top_t2 = np.stack([v01, v10, v11], axis=1)

    # 2. Bottom surface vertices (at flat base_z)
    b00 = np.stack([grid_x[r_idx, c_idx], grid_y[r_idx, c_idx], np.full(len(r_idx), base_z)], axis=-1)
    b01 = np.stack([grid_x[r_idx, c_idx+1], grid_y[r_idx, c_idx+1], np.full(len(r_idx), base_z)], axis=-1)
    b10 = np.stack([grid_x[r_idx+1, c_idx], grid_y[r_idx+1, c_idx], np.full(len(r_idx), base_z)], axis=-1)
    b11 = np.stack([grid_x[r_idx+1, c_idx+1], grid_y[r_idx+1, c_idx+1], np.full(len(r_idx), base_z)], axis=-1)

    # Inverted winding order so normals point down (-Z)
    bot_t1 = np.stack([b00, b01, b10], axis=1)
    bot_t2 = np.stack([b01, b11, b10], axis=1)

    # 3. Dynamic Boundary Walls along perimeter (Watertight Manifold)
    # North boundary (r=0 or upper neighbor is invalid)
    n_mask = quad_valid & np.vstack([np.ones((1, C - 1), dtype=bool), ~quad_valid[:-1, :]])
    n_r, n_c = np.where(n_mask)
    nw_t00 = np.stack([grid_x[n_r, n_c], grid_y[n_r, n_c], zs[n_r, n_c]], axis=-1)
    nw_t01 = np.stack([grid_x[n_r, n_c+1], grid_y[n_r, n_c+1], zs[n_r, n_c+1]], axis=-1)
    nw_b00 = np.stack([grid_x[n_r, n_c], grid_y[n_r, n_c], np.full(len(n_r), base_z)], axis=-1)
    nw_b01 = np.stack([grid_x[n_r, n_c+1], grid_y[n_r, n_c+1], np.full(len(n_r), base_z)], axis=-1)
    nw_t1 = np.stack([nw_t00, nw_t01, nw_b00], axis=1)
    nw_t2 = np.stack([nw_t01, nw_b01, nw_b00], axis=1)

    # South boundary (r=R-2 or lower neighbor is invalid)
    s_mask = quad_valid & np.vstack([~quad_valid[1:, :], np.ones((1, C - 1), dtype=bool)])
    s_r, s_c = np.where(s_mask)
    sw_t10 = np.stack([grid_x[s_r+1, s_c], grid_y[s_r+1, s_c], zs[s_r+1, s_c]], axis=-1)
    sw_t11 = np.stack([grid_x[s_r+1, s_c+1], grid_y[s_r+1, s_c+1], zs[s_r+1, s_c+1]], axis=-1)
    sw_b10 = np.stack([grid_x[s_r+1, s_c], grid_y[s_r+1, s_c], np.full(len(s_r), base_z)], axis=-1)
    sw_b11 = np.stack([grid_x[s_r+1, s_c+1], grid_y[s_r+1, s_c+1], np.full(len(s_r), base_z)], axis=-1)
    sw_t1 = np.stack([sw_t11, sw_t10, sw_b10], axis=1)
    sw_t2 = np.stack([sw_t11, sw_b10, sw_b11], axis=1)

    # West boundary (c=0 or left neighbor is invalid)
    w_mask = quad_valid & np.hstack([np.ones((R - 1, 1), dtype=bool), ~quad_valid[:, :-1]])
    w_r, w_c = np.where(w_mask)
    ww_t00 = np.stack([grid_x[w_r, w_c], grid_y[w_r, w_c], zs[w_r, w_c]], axis=-1)
    ww_t10 = np.stack([grid_x[w_r+1, w_c], grid_y[w_r+1, w_c], zs[w_r+1, w_c]], axis=-1)
    ww_b00 = np.stack([grid_x[w_r, w_c], grid_y[w_r, w_c], np.full(len(w_r), base_z)], axis=-1)
    ww_b10 = np.stack([grid_x[w_r+1, w_c], grid_y[w_r+1, w_c], np.full(len(w_r), base_z)], axis=-1)
    ww_t1 = np.stack([ww_t10, ww_t00, ww_b00], axis=1)
    ww_t2 = np.stack([ww_t10, ww_b00, ww_b10], axis=1)

    # East boundary (c=C-2 or right neighbor is invalid)
    e_mask = quad_valid & np.hstack([~quad_valid[:, 1:], np.ones((R - 1, 1), dtype=bool)])
    e_r, e_c = np.where(e_mask)
    ew_t01 = np.stack([grid_x[e_r, e_c+1], grid_y[e_r, e_c+1], zs[e_r, e_c+1]], axis=-1)
    ew_t11 = np.stack([grid_x[e_r+1, e_c+1], grid_y[e_r+1, e_c+1], zs[e_r+1, e_c+1]], axis=-1)
    ew_b01 = np.stack([grid_x[e_r, e_c+1], grid_y[e_r, e_c+1], np.full(len(e_r), base_z)], axis=-1)
    ew_b11 = np.stack([grid_x[e_r+1, e_c+1], grid_y[e_r+1, e_c+1], np.full(len(e_r), base_z)], axis=-1)
    ew_t1 = np.stack([ew_t01, ew_t11, ew_b11], axis=1)
    ew_t2 = np.stack([ew_t01, ew_b11, ew_b01], axis=1)

    all_triangles = np.concatenate([
        top_t1, top_t2,
        bot_t1, bot_t2,
        nw_t1, nw_t2,
        sw_t1, sw_t2,
        ww_t1, ww_t2,
        ew_t1, ew_t2
    ], axis=0)

    return all_triangles

def export_binary_stl(triangles, output_stream):
    """
    Serializes triangle array (N, 3, 3) into binary STL format in streaming chunks.
    Ensures low memory footprint even with millions of facets.
    """
    n_tris = len(triangles)
    header_text = b'DivinoGIS Watertight Solid STL (High-Res 3D Topo)'
    header = header_text + b'\0' * (80 - len(header_text))

    output_stream.write(header)
    output_stream.write(np.uint32(n_tris).tobytes())

    # Stream in blocks of 100,000 triangles to keep memory usage minimal
    block_size = 100000
    facet_dtype = np.dtype([
        ('normal', ('<f4', 3)),
        ('v0', ('<f4', 3)),
        ('v1', ('<f4', 3)),
        ('v2', ('<f4', 3)),
        ('attr', '<u2')
    ])

    for i in range(0, n_tris, block_size):
        chunk_tris = triangles[i:i + block_size]
        v0 = chunk_tris[:, 0, :]
        v1 = chunk_tris[:, 1, :]
        v2 = chunk_tris[:, 2, :]
        cross = np.cross(v1 - v0, v2 - v0)
        norm = np.linalg.norm(cross, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        normals = (cross / norm).astype(np.float32)

        facets = np.empty(len(chunk_tris), dtype=facet_dtype)
        facets['normal'] = normals
        facets['v0'] = v0.astype(np.float32)
        facets['v1'] = v1.astype(np.float32)
        facets['v2'] = v2.astype(np.float32)
        facets['attr'] = 0
        output_stream.write(facets.tobytes())

def generate_stl_from_geotiff(
    tif_path,
    scale_denom=50000.0,
    vertical_exag=2.0,
    base_thickness_mm=0.0,
    smoothing_level=0.0,
    max_grid=1000
):
    """
    Converts GeoTIFF raster into a solid, 3D printable binary STL.
    - Preserves high-density detail (default max_grid=1000 equivalent to DEMto3D ~0.2mm).
    - If base_thickness_mm is 0, the lowest point of the terrain is flush with Z=0 (no extra base).
    - If raster has NoData (polygon cutline), automatically sculpts the contour of the polygon
      with vertical perimeter walls and excludes empty space outside the polygon.
    Returns: (stl_bytes, metadata_dict)
    """
    base_thickness_mm = max(0.0, float(base_thickness_mm))
    smoothing_level = max(0.0, float(smoothing_level))
    max_grid = max(100, int(max_grid))

    with rasterio.open(tif_path) as src:
        bounds = {
            'min_lat': src.bounds.bottom,
            'max_lat': src.bounds.top,
            'min_lon': src.bounds.left,
            'max_lon': src.bounds.right
        }

        width_m, height_m = calculate_real_world_dimensions(bounds)

        # Determine grid resolution
        aspect = width_m / max(1.0, height_m)
        if aspect >= 1.0:
            nx = min(max_grid, src.width)
            ny = max(16, int(round(nx / aspect)))
        else:
            ny = min(max_grid, src.height)
            nx = max(16, int(round(ny * aspect)))

        # Resample elevation data
        dem = src.read(1, out_shape=(ny, nx), resampling=Resampling.bilinear).astype(np.float32)
        nodata = src.nodata

        if nodata is not None:
            valid = (dem != nodata) & (dem > -1000) & (dem < 9000)
        else:
            valid = (dem > -1000) & (dem < 9000)

        if not np.any(valid):
            raise ValueError("O raster não contém dados de elevação válidos.")

        min_elev_m = float(np.min(dem[valid]))
        max_elev_m = float(np.max(dem[valid]))

        # Fill invalid cells with min_elev_m to keep numerical consistency during optional smoothing
        dem[~valid] = min_elev_m

        # Apply Gaussian smoothing only if requested by user (smoothing_level > 0)
        if smoothing_level > 0:
            sigma = float(smoothing_level) * 0.8
            dem = gaussian_filter(dem, sigma=sigma)
            min_elev_m = float(np.min(dem[valid]))
            max_elev_m = float(np.max(dem[valid]))

        delta_z_m = max(0.1, max_elev_m - min_elev_m)

        # Model width & length in mm (1 m = 1000 mm)
        width_mm = round((width_m * 1000.0) / scale_denom, 2)
        length_mm = round((height_m * 1000.0) / scale_denom, 2)

        # Model relief height in mm
        relief_height_mm = round(((delta_z_m * 1000.0) / scale_denom) * vertical_exag, 2)
        total_height_mm = round(base_thickness_mm + relief_height_mm, 2)

        # Coordinates grid in mm
        xs = np.linspace(0.0, width_mm, nx, dtype=np.float32)
        # Row 0 is top (North), Y decreases towards South
        ys = np.linspace(length_mm, 0.0, ny, dtype=np.float32)

        # Z elevations in mm
        norm_z = (dem - min_elev_m) / delta_z_m
        zs = (base_thickness_mm + (norm_z * relief_height_mm)).astype(np.float32)

        # Build watertight solid mesh conforming to polygon mask
        triangles = build_solid_stl_mesh(xs, ys, zs, valid_mask=valid, base_z=0.0)

        # Stream into in-memory buffer
        buf = io.BytesIO()
        export_binary_stl(triangles, buf)
        stl_bytes = buf.getvalue()

        metadata = {
            'width_mm': width_mm,
            'length_mm': length_mm,
            'relief_height_mm': relief_height_mm,
            'base_thickness_mm': round(base_thickness_mm, 2),
            'total_height_mm': total_height_mm,
            'real_width_km': round(width_m / 1000.0, 2),
            'real_length_km': round(height_m / 1000.0, 2),
            'real_delta_z_m': round(delta_z_m, 1),
            'scale_denom': int(scale_denom),
            'vertical_exag': round(vertical_exag, 1),
            'smoothing_level': round(smoothing_level, 1),
            'max_grid': max_grid,
            'triangles_count': len(triangles),
            'file_size_kb': round(len(stl_bytes) / 1024.0, 1)
        }

        return stl_bytes, metadata
