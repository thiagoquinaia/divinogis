import os
import requests
from flask import Flask, render_template, request, jsonify, send_file, abort
import srtm_service

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

EXPORTS_DIR = os.path.join(os.path.dirname(__file__), 'exports')

# In-memory storage of layers for the current session
SESSION_LAYERS = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/srtm', methods=['POST'])
def request_srtm():
    try:
        data = request.get_json(force=True)
        min_lat = float(data.get('min_lat'))
        min_lon = float(data.get('min_lon'))
        max_lat = float(data.get('max_lat'))
        max_lon = float(data.get('max_lon'))
        layer_name = data.get('name') or f"SRTM_30m_{len(SESSION_LAYERS) + 1}"
        colormap = data.get('colormap', 'terrain')
        hillshade = data.get('hillshade', True)

        # Validate coordinates
        if min_lat >= max_lat or min_lon >= max_lon:
            return jsonify({'error': 'Coordenadas inválidas. min_lat/min_lon devem ser menores que max_lat/max_lon.'}), 400

        result = srtm_service.fetch_srtm_dem(
            min_lat, min_lon, max_lat, max_lon,
            colormap=colormap,
            blend_hillshade=hillshade
        )

        result['name'] = layer_name
        SESSION_LAYERS[result['id']] = result

        return jsonify({
            'success': True,
            'layer': result
        })
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Falha no processamento SRTM: {str(e)}'}), 500

@app.route('/api/download/<layer_id>', methods=['GET'])
@app.route('/api/download/<layer_id>.tif', methods=['GET'])
@app.route('/api/download/<layer_id>.tiff', methods=['GET'])
def download_geotiff(layer_id):
    clean_id = layer_id.replace('.tiff', '').replace('.tif', '')
    tif_path = os.path.join(EXPORTS_DIR, f"{clean_id}.tif")
    
    if not os.path.exists(tif_path):
        abort(404, description="Arquivo GeoTIFF não encontrado.")

    layer_info = SESSION_LAYERS.get(clean_id)
    download_name = f"{layer_info['name']}.tif" if layer_info else f"{clean_id}.tif"
    
    return send_file(
        tif_path,
        mimetype='image/tiff',
        as_attachment=True,
        download_name=download_name
    )

@app.route('/api/preview/<layer_id>', methods=['GET'])
@app.route('/api/preview/<layer_id>.png', methods=['GET'])
def preview_png(layer_id):
    clean_id = layer_id.replace('.png', '')
    png_path = os.path.join(EXPORTS_DIR, f"{clean_id}.png")
    
    if not os.path.exists(png_path):
        abort(404, description="Visualização raster não encontrada.")

    return send_file(
        png_path,
        mimetype='image/png',
        as_attachment=False
    )

@app.route('/api/elevation-grid/<layer_id>', methods=['GET'])
def get_elevation_grid(layer_id):
    clean_id = layer_id.replace('.tiff', '').replace('.tif', '').replace('.png', '')
    tif_path = os.path.join(EXPORTS_DIR, f"{clean_id}.tif")
    if not os.path.exists(tif_path):
        abort(404, description="Arquivo GeoTIFF não encontrado.")

    try:
        import rasterio
        from rasterio.enums import Resampling
        import numpy as np

        with rasterio.open(tif_path) as src:
            target_size = 120
            aspect = src.width / max(1, src.height)
            if aspect >= 1.0:
                nx = target_size
                ny = max(16, int(round(target_size / aspect)))
            else:
                ny = target_size
                nx = max(16, int(round(target_size * aspect)))

            data = src.read(1, out_shape=(ny, nx), resampling=Resampling.bilinear).astype(float)
            nodata = src.nodata
            valid = (data != nodata) & (data > -1000) & (data < 9000)
            if np.any(valid):
                min_z = float(np.min(data[valid]))
                max_z = float(np.max(data[valid]))
            else:
                min_z = 0.0
                max_z = 1.0

            data[~valid] = min_z

            return jsonify({
                'nx': nx,
                'ny': ny,
                'min_elev': min_z,
                'max_elev': max_z,
                'elevations': data.flatten().tolist()
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/elevation', methods=['GET'])
def query_elevation():
    layer_id = request.args.get('layer_id')
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    if not layer_id or lat is None or lon is None:
        return jsonify({'error': 'Parâmetros layer_id, lat e lon são obrigatórios.'}), 400

    elev = srtm_service.get_elevation_at_point(layer_id, lat, lon)
    if elev is None:
        return jsonify({'success': False, 'message': 'Fora da área da camada ou sem dados.'})

    return jsonify({'success': True, 'elevation': elev, 'lat': lat, 'lon': lon})

@app.route('/api/search', methods=['GET'])
def search_location():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    try:
        headers = {'User-Agent': 'QGIS-Web-SRTM30m/1.0'}
        url = 'https://nominatim.openstreetmap.org/search'
        params = {
            'q': query,
            'format': 'json',
            'limit': 5,
            'addressdetails': 1
        }
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200:
            return jsonify(resp.json())
        return jsonify([])
    except Exception:
        return jsonify([])

@app.route('/api/layers', methods=['GET'])
def list_layers():
    return jsonify(list(SESSION_LAYERS.values()))

@app.route('/api/layers/<layer_id>', methods=['DELETE'])
def delete_layer(layer_id):
    clean_id = layer_id.replace('.tif', '').replace('.png', '')
    if clean_id in SESSION_LAYERS:
        del SESSION_LAYERS[clean_id]
        
    tif_path = os.path.join(EXPORTS_DIR, f"{clean_id}.tif")
    png_path = os.path.join(EXPORTS_DIR, f"{clean_id}.png")
    if os.path.exists(tif_path):
        try: os.remove(tif_path)
        except Exception: pass
    if os.path.exists(png_path):
        try: os.remove(png_path)
        except Exception: pass

    return jsonify({'success': True})

@app.route('/api/export-stl', methods=['POST'])
def export_stl():
    try:
        import stl_service
        data = request.get_json(force=True)
        layer_id = data.get('layer_id', '').replace('.tif', '').replace('.tiff', '').replace('.png', '')
        tif_path = os.path.join(EXPORTS_DIR, f"{layer_id}.tif")

        if not os.path.exists(tif_path):
            return jsonify({'error': 'Arquivo GeoTIFF da camada não encontrado.'}), 404

        scale_denom = float(data.get('scale_denom', 50000.0))
        vertical_exag = float(data.get('vertical_exag', 2.0))
        base_thickness_mm = float(data.get('base_thickness_mm', 3.0))
        smoothing_level = float(data.get('smoothing_level', 1.0))

        stl_bytes, meta = stl_service.generate_stl_from_geotiff(
            tif_path=tif_path,
            scale_denom=scale_denom,
            vertical_exag=vertical_exag,
            base_thickness_mm=base_thickness_mm,
            smoothing_level=smoothing_level
        )

        stl_filename = f"{layer_id}_1_{int(scale_denom)}_exag{vertical_exag}x.stl"
        stl_path = os.path.join(EXPORTS_DIR, stl_filename)
        with open(stl_path, 'wb') as f:
            f.write(stl_bytes)

        return jsonify({
            'success': True,
            'filename': stl_filename,
            'download_url': f"/api/download-stl/{stl_filename}",
            'metadata': meta
        })
    except Exception as e:
        return jsonify({'error': f'Erro ao gerar modelo STL: {str(e)}'}), 500

@app.route('/api/download-stl/<path:filename>', methods=['GET'])
def download_stl(filename):
    clean_filename = os.path.basename(filename)
    stl_path = os.path.join(EXPORTS_DIR, clean_filename)
    if not os.path.exists(stl_path):
        abort(404, description="Arquivo STL não encontrado.")

    return send_file(
        stl_path,
        mimetype='application/sla',
        as_attachment=True,
        download_name=clean_filename
    )

# ==============================================================
# ENDPOINTS IBGE: Malhas Vetoriais Oficiais & Exportação
# ==============================================================
@app.route('/api/ibge/ufs', methods=['GET'])
def get_ibge_ufs():
    import ibge_service
    ufs_list = [
        {'code': cod, 'sigla': data['sigla'], 'nome': data['nome'], 'regiao': data['regiao']}
        for cod, data in sorted(ibge_service.UF_MAP.items(), key=lambda x: x[1]['nome'])
    ]
    return jsonify(ufs_list)

@app.route('/api/ibge/mesh', methods=['GET'])
def get_ibge_mesh():
    mesh_type = request.args.get('type', 'estados').lower()
    uf_code = request.args.get('uf', None)
    try:
        import ibge_service
        geojson_data = ibge_service.fetch_ibge_mesh(mesh_type, uf_code)
        features = geojson_data.get('features', [])
        feature_count = len(features)

        # Define nome amigável da camada
        uf_name = uf_code
        if uf_code and uf_code in ibge_service.UF_BY_SIGLA:
            uf_name = ibge_service.UF_BY_SIGLA[uf_code]['nome']

        mesh_names = {
            'brasil': 'IBGE - Contorno do Brasil',
            'regioes': 'IBGE - Regiões do Brasil',
            'estados': 'IBGE - Estados / UFs',
            'mesorregioes_brasil': 'IBGE - Mesorregiões do Brasil (137)',
            'mesorregioes': f'IBGE - Mesorregiões ({uf_name or "Brasil"})',
            'municipios': f'IBGE - Municípios ({uf_name or "UF"})'
        }
        layer_name = mesh_names.get(mesh_type, f'IBGE - {mesh_type.capitalize()}')

        # Identifica campos disponíveis
        fields = []
        if features and 'properties' in features[0]:
            fields = list(features[0]['properties'].keys())

        import time
        layer_id = f"ibge_{mesh_type}_{int(time.time()*1000)}"

        return jsonify({
            'success': True,
            'layer': {
                'id': layer_id,
                'name': layer_name,
                'type': 'vector',
                'mesh_type': mesh_type,
                'uf': uf_code,
                'feature_count': feature_count,
                'fields': fields,
                'geojson': geojson_data
            }
        })
    except Exception as e:
        return jsonify({'error': f'Erro ao obter malha IBGE: {str(e)}'}), 500

@app.route('/api/ibge/export', methods=['POST'])
def export_ibge_vector():
    try:
        import ibge_service
        data = request.get_json(force=True)
        geojson_data = data.get('geojson')
        layer_name = data.get('layer_name', 'Camada_IBGE')
        format_type = data.get('format', 'gpkg')
        target_crs = data.get('target_crs') or data.get('crs', 'EPSG:4674')

        if not geojson_data:
            return jsonify({'error': 'GeoJSON da camada é obrigatório.'}), 400

        out_path, filename, mimetype = ibge_service.export_vector(
            geojson_data=geojson_data,
            layer_name=layer_name,
            format_type=format_type,
            target_crs=target_crs
        )

        features = geojson_data.get('features', [])
        return jsonify({
            'success': True,
            'filename': filename,
            'download_url': f"/api/download-vector/{filename}",
            'format': format_type,
            'crs': target_crs,
            'feature_count': len(features),
            'file_size_kb': round(os.path.getsize(out_path) / 1024.0, 1)
        })
    except Exception as e:
        return jsonify({'error': f'Erro ao exportar camada vetorial: {str(e)}'}), 500

@app.route('/api/download-vector/<path:filename>', methods=['GET'])
def download_vector(filename):
    clean_filename = os.path.basename(filename)
    vector_path = os.path.join(EXPORTS_DIR, clean_filename)
    if not os.path.exists(vector_path):
        abort(404, description="Arquivo vetorial não encontrado.")

    ext = os.path.splitext(clean_filename)[1].lower()
    mimetypes = {
        '.gpkg': 'application/geopackage+sqlite3',
        '.kml': 'application/vnd.google-earth.kml+xml',
        '.geojson': 'application/geo+json',
        '.json': 'application/geo+json',
        '.zip': 'application/zip'
    }

    return send_file(
        vector_path,
        mimetype=mimetypes.get(ext, 'application/octet-stream'),
        as_attachment=True,
        download_name=clean_filename
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"\n=======================================================")
    print(f"  DivinoGIS - Gerador Topo 3D (SRTM 30m) & Malhas IBGE")
    print(f"  Acesse no navegador: http://localhost:{port}")
    print(f"=======================================================\n")
    app.run(host='0.0.0.0', port=port, debug=True)
