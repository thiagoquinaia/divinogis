import io
import struct
import numpy as np
import pytest
import stl_service

def verify_triangles_watertight(triangles, decimals=3):
    """
    Verifica matematicamente se um array de triangulos (N, 3, 3) forma um solido 2-manifold fechado (watertight).
    Arredonda os vertices para `decimals` casas para unir vertices geometricamente coincidentes,
    e verifica se toda aresta nao-orientada (u, v) e compartilhada por exatamente 2 triangulos.
    """
    rounded = np.round(triangles, decimals=decimals)
    
    # Mapeia cada coordenada 3D unica para um indice inteiro
    vertex_map = {}
    next_idx = 0
    tri_indices = []

    for tri in rounded:
        indices = []
        for v in tri:
            key = (float(v[0]), float(v[1]), float(v[2]))
            if key not in vertex_map:
                vertex_map[key] = next_idx
                next_idx += 1
            indices.append(vertex_map[key])
        tri_indices.append(indices)

    edge_counts = {}
    for tri in tri_indices:
        edges = [
            (tri[0], tri[1]),
            (tri[1], tri[2]),
            (tri[2], tri[0])
        ]
        for u, v in edges:
            if u == v:
                continue # triangulo degenerado
            canonical_edge = (min(u, v), max(u, v))
            edge_counts[canonical_edge] = edge_counts.get(canonical_edge, 0) + 1

    open_edges = [edge for edge, count in edge_counts.items() if count != 2]
    return len(open_edges) == 0, len(open_edges)

def test_build_solid_stl_mesh_rectangular():
    """Testa malha solida retangular completa (sem NoData)."""
    ny, nx = 8, 8
    xs = np.linspace(0, 100, nx, dtype=np.float32)
    ys = np.linspace(100, 0, ny, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(xs, ys)
    zs = (2.0 + np.sin(grid_x / 20.0) * np.cos(grid_y / 20.0)).astype(np.float32)

    triangles = stl_service.build_solid_stl_mesh(xs, ys, zs, valid_mask=None, base_z=0.0)
    assert len(triangles) > 0
    assert triangles.ndim == 3
    assert triangles.shape[1:] == (3, 3)

    is_watertight, open_edge_count = verify_triangles_watertight(triangles)
    assert is_watertight, f"Malha retangular deve ser 100% estanque, mas encontrou {open_edge_count} arestas abertas"

    # Z minimo deve ser exatamente base_z (0.0)
    min_z = float(np.min(triangles[:, :, 2]))
    assert np.isclose(min_z, 0.0, atol=1e-5)

def test_build_solid_stl_mesh_with_nodata_cutline():
    """Testa malha com mascara NoData (recorte por poligono perimetral)."""
    ny, nx = 14, 14
    xs = np.linspace(0, 100, nx, dtype=np.float32)
    ys = np.linspace(100, 0, ny, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(xs, ys)
    zs = (3.0 + np.sin(grid_x / 15.0)).astype(np.float32)

    # Mascara circular no centro (valido no centro, invalido nas bordas)
    center_dist = np.sqrt((grid_x - 50)**2 + (grid_y - 50)**2)
    valid_mask = center_dist < 40.0

    triangles = stl_service.build_solid_stl_mesh(xs, ys, zs, valid_mask=valid_mask, base_z=0.0)
    assert len(triangles) > 0

    is_watertight, open_edge_count = verify_triangles_watertight(triangles)
    assert is_watertight, f"Malha recortada por poligono deve ser estanque, mas encontrou {open_edge_count} arestas abertas"

    # Base z = 0.0
    min_z = float(np.min(triangles[:, :, 2]))
    assert np.isclose(min_z, 0.0, atol=1e-5)

def test_base_thickness_zero():
    """Testa que base_z = 0.0 coloca a cota minima exatamente em 0.0 mm."""
    ny, nx = 6, 6
    xs = np.linspace(0, 50, nx, dtype=np.float32)
    ys = np.linspace(50, 0, ny, dtype=np.float32)
    zs = np.ones((ny, nx), dtype=np.float32) * 5.0 # relevo plano 5mm

    triangles = stl_service.build_solid_stl_mesh(xs, ys, zs, valid_mask=None, base_z=0.0)
    min_z = float(np.min(triangles[:, :, 2]))
    assert np.isclose(min_z, 0.0, atol=1e-5)

def test_export_binary_stl_structure():
    """Verifica se o binario STL gerado obedece estritamente a especificacao padrao STL binario."""
    triangles = np.array([
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0]
        ]
    ], dtype=np.float32)

    buf = io.BytesIO()
    stl_service.export_binary_stl(triangles, buf)
    stl_bytes = buf.getvalue()

    # Formato: 80 bytes cabecalho + 4 bytes uint32 contagem de triangulos + (num_triangulos * 50 bytes)
    expected_len = 80 + 4 + (1 * 50)
    assert len(stl_bytes) == expected_len

    # Verifica uint32 na posicao 80:84
    tri_count = struct.unpack('<I', stl_bytes[80:84])[0]
    assert tri_count == 1

def test_generate_stl_from_geotiff(sample_dem_geotiff):
    """Teste fim-a-fim da funcao generate_stl_from_geotiff usando o fixture sintetico."""
    tif_path = sample_dem_geotiff['path']
    stl_bytes, meta = stl_service.generate_stl_from_geotiff(
        tif_path=tif_path,
        scale_denom=10000.0,
        vertical_exag=1.5,
        base_thickness_mm=0.0,
        smoothing_level=0.0,
        max_grid=50
    )

    assert isinstance(stl_bytes, (bytes, bytearray))
    assert len(stl_bytes) > 84
    assert meta['triangles_count'] > 0
    assert meta['base_thickness_mm'] == 0.0
    assert meta['relief_height_mm'] > 0.0
    assert meta['total_height_mm'] >= meta['relief_height_mm']
    assert meta['width_mm'] > 0.0
    assert meta['length_mm'] > 0.0
