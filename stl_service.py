import os
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

def build_solid_stl_mesh(xs, ys, zs, base_z=0.0):
    """
    Constructs a watertight, closed 2-manifold STL triangular mesh
    with top terrain, 4 side walls, and a flat bottom at base_z.
    xs: 1D array of length C (X coordinates in mm)
    ys: 1D array of length R (Y coordinates in mm)
    zs: 2D array of shape (R, C) (Z elevations in mm)
    """
    R, C = zs.shape
    grid_x, grid_y = np.meshgrid(xs, ys)

    r_idx, c_idx = np.meshgrid(np.arange(R - 1), np.arange(C - 1), indexing='ij')

    # Top surface vertices
    v00 = np.stack([grid_x[r_idx, c_idx], grid_y[r_idx, c_idx], zs[r_idx, c_idx]], axis=-1)
    v01 = np.stack([grid_x[r_idx, c_idx+1], grid_y[r_idx, c_idx+1], zs[r_idx, c_idx+1]], axis=-1)
    v10 = np.stack([grid_x[r_idx+1, c_idx], grid_y[r_idx+1, c_idx], zs[r_idx+1, c_idx]], axis=-1)
    v11 = np.stack([grid_x[r_idx+1, c_idx+1], grid_y[r_idx+1, c_idx+1], zs[r_idx+1, c_idx+1]], axis=-1)

    top_t1 = np.stack([v00, v10, v01], axis=-2).reshape(-1, 3, 3)
    top_t2 = np.stack([v01, v10, v11], axis=-2).reshape(-1, 3, 3)

    # Bottom surface vertices (at base_z = 0)
    b00 = np.stack([grid_x[r_idx, c_idx], grid_y[r_idx, c_idx], np.full_like(zs[r_idx, c_idx], base_z)], axis=-1)
    b01 = np.stack([grid_x[r_idx, c_idx+1], grid_y[r_idx, c_idx+1], np.full_like(zs[r_idx, c_idx+1], base_z)], axis=-1)
    b10 = np.stack([grid_x[r_idx+1, c_idx], grid_y[r_idx+1, c_idx], np.full_like(zs[r_idx+1, c_idx], base_z)], axis=-1)
    b11 = np.stack([grid_x[r_idx+1, c_idx+1], grid_y[r_idx+1, c_idx+1], np.full_like(zs[r_idx+1, c_idx+1], base_z)], axis=-1)

    # Inverted winding order for bottom so normals point outward/downwards
    bot_t1 = np.stack([b00, b01, b10], axis=-2).reshape(-1, 3, 3)
    bot_t2 = np.stack([b01, b11, b10], axis=-2).reshape(-1, 3, 3)

    # Side walls
    # North wall (r = 0)
    c_w = np.arange(C - 1)
    nw_t00 = np.stack([grid_x[0, c_w], grid_y[0, c_w], zs[0, c_w]], axis=-1)
    nw_t01 = np.stack([grid_x[0, c_w+1], grid_y[0, c_w+1], zs[0, c_w+1]], axis=-1)
    nw_b00 = np.stack([grid_x[0, c_w], grid_y[0, c_w], np.full(C-1, base_z)], axis=-1)
    nw_b01 = np.stack([grid_x[0, c_w+1], grid_y[0, c_w+1], np.full(C-1, base_z)], axis=-1)
    nw_t1 = np.stack([nw_t00, nw_t01, nw_b00], axis=-2).reshape(-1, 3, 3)
    nw_t2 = np.stack([nw_t01, nw_b01, nw_b00], axis=-2).reshape(-1, 3, 3)

    # South wall (r = R - 1)
    sw_t00 = np.stack([grid_x[R-1, c_w], grid_y[R-1, c_w], zs[R-1, c_w]], axis=-1)
    sw_t01 = np.stack([grid_x[R-1, c_w+1], grid_y[R-1, c_w+1], zs[R-1, c_w+1]], axis=-1)
    sw_b00 = np.stack([grid_x[R-1, c_w], grid_y[R-1, c_w], np.full(C-1, base_z)], axis=-1)
    sw_b01 = np.stack([grid_x[R-1, c_w+1], grid_y[R-1, c_w+1], np.full(C-1, base_z)], axis=-1)
    sw_t1 = np.stack([sw_t00, sw_b00, sw_t01], axis=-2).reshape(-1, 3, 3)
    sw_t2 = np.stack([sw_t01, sw_b00, sw_b01], axis=-2).reshape(-1, 3, 3)

    # West wall (c = 0)
    r_w = np.arange(R - 1)
    ww_t00 = np.stack([grid_x[r_w, 0], grid_y[r_w, 0], zs[r_w, 0]], axis=-1)
    ww_t10 = np.stack([grid_x[r_w+1, 0], grid_y[r_w+1, 0], zs[r_w+1, 0]], axis=-1)
    ww_b00 = np.stack([grid_x[r_w, 0], grid_y[r_w, 0], np.full(R-1, base_z)], axis=-1)
    ww_b10 = np.stack([grid_x[r_w+1, 0], grid_y[r_w+1, 0], np.full(R-1, base_z)], axis=-1)
    ww_t1 = np.stack([ww_t00, ww_b00, ww_t10], axis=-2).reshape(-1, 3, 3)
    ww_t2 = np.stack([ww_t10, ww_b00, ww_b10], axis=-2).reshape(-1, 3, 3)

    # East wall (c = C - 1)
    ew_t00 = np.stack([grid_x[r_w, C-1], grid_y[r_w, C-1], zs[r_w, C-1]], axis=-1)
    ew_t10 = np.stack([grid_x[r_w+1, C-1], grid_y[r_w+1, C-1], zs[r_w+1, C-1]], axis=-1)
    ew_b00 = np.stack([grid_x[r_w, C-1], grid_y[r_w, C-1], np.full(R-1, base_z)], axis=-1)
    ew_b10 = np.stack([grid_x[r_w+1, C-1], grid_y[r_w+1, C-1], np.full(R-1, base_z)], axis=-1)
    ew_t1 = np.stack([ew_t00, ew_t10, ew_b00], axis=-2).reshape(-1, 3, 3)
    ew_t2 = np.stack([ew_t10, ew_b10, ew_b00], axis=-2).reshape(-1, 3, 3)

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
    Serializes triangle array (N, 3, 3) into binary STL format.
    """
    n_tris = len(triangles)

    # Calculate face normals
    v0 = triangles[:, 0, :]
    v1 = triangles[:, 1, :]
    v2 = triangles[:, 2, :]
    cross = np.cross(v1 - v0, v2 - v0)
    norm = np.linalg.norm(cross, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    normals = (cross / norm).astype(np.float32)

    facet_dtype = np.dtype([
        ('normal', ('<f4', 3)),
        ('v0', ('<f4', 3)),
        ('v1', ('<f4', 3)),
        ('v2', ('<f4', 3)),
        ('attr', '<u2')
    ])

    facets = np.empty(n_tris, dtype=facet_dtype)
    facets['normal'] = normals
    facets['v0'] = v0.astype(np.float32)
    facets['v1'] = v1.astype(np.float32)
    facets['v2'] = v2.astype(np.float32)
    facets['attr'] = 0

    header_text = b'QGIS-Web-Topo3D Watertight Solid STL'
    header = header_text + b'\0' * (80 - len(header_text))

    output_stream.write(header)
    output_stream.write(np.uint32(n_tris).tobytes())
    output_stream.write(facets.tobytes())

def generate_stl_from_geotiff(tif_path, scale_denom=50000.0, vertical_exag=2.0, base_thickness_mm=3.0, smoothing_level=1.0, max_grid=200):
    """
    Converts GeoTIFF raster into a solid, 3D printable binary STL.
    Returns: (stl_bytes, metadata_dict)
    """
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

        valid = (dem != nodata) & (dem > -1000) & (dem < 9000)
        min_elev_m = float(np.min(dem[valid])) if np.any(valid) else 0.0
        max_elev_m = float(np.max(dem[valid])) if np.any(valid) else 1.0
        dem[~valid] = min_elev_m

        # Apply Gaussian smoothing if requested (sigma > 0)
        if smoothing_level > 0:
            # Scale sigma according to level (e.g. 0.5 to 3.0)
            sigma = float(smoothing_level) * 0.8
            dem = gaussian_filter(dem, sigma=sigma)
            # Re-verify min/max after filter
            min_elev_m = float(np.min(dem))
            max_elev_m = float(np.max(dem))

        delta_z_m = max(0.1, max_elev_m - min_elev_m)

        # Scale calculation: 1 m = 1000 mm
        # Model width & length in mm
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

        # Build watertight solid mesh
        triangles = build_solid_stl_mesh(xs, ys, zs, base_z=0.0)

        # Stream into in-memory buffer
        import io
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
            'triangles_count': len(triangles),
            'file_size_kb': round(len(stl_bytes) / 1024.0, 1)
        }

        return stl_bytes, metadata
