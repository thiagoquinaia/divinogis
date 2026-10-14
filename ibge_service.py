import os
import math
import json
import xml.etree.ElementTree as ET
import requests
import geopandas as gpd
from shapely.geometry import shape

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'data_cache', 'ibge')
EXPORTS_DIR = os.path.join(os.path.dirname(__file__), 'exports')

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

UF_MAP = {
    '11': {'nome': 'Rondônia', 'sigla': 'RO', 'regiao': 'Norte'},
    '12': {'nome': 'Acre', 'sigla': 'AC', 'regiao': 'Norte'},
    '13': {'nome': 'Amazonas', 'sigla': 'AM', 'regiao': 'Norte'},
    '14': {'nome': 'Roraima', 'sigla': 'RR', 'regiao': 'Norte'},
    '15': {'nome': 'Pará', 'sigla': 'PA', 'regiao': 'Norte'},
    '16': {'nome': 'Amapá', 'sigla': 'AP', 'regiao': 'Norte'},
    '17': {'nome': 'Tocantins', 'sigla': 'TO', 'regiao': 'Norte'},
    '21': {'nome': 'Maranhão', 'sigla': 'MA', 'regiao': 'Nordeste'},
    '22': {'nome': 'Piauí', 'sigla': 'PI', 'regiao': 'Nordeste'},
    '23': {'nome': 'Ceará', 'sigla': 'CE', 'regiao': 'Nordeste'},
    '24': {'nome': 'Rio Grande do Norte', 'sigla': 'RN', 'regiao': 'Nordeste'},
    '25': {'nome': 'Paraíba', 'sigla': 'PB', 'regiao': 'Nordeste'},
    '26': {'nome': 'Pernambuco', 'sigla': 'PE', 'regiao': 'Nordeste'},
    '27': {'nome': 'Alagoas', 'sigla': 'AL', 'regiao': 'Nordeste'},
    '28': {'nome': 'Sergipe', 'sigla': 'SE', 'regiao': 'Nordeste'},
    '29': {'nome': 'Bahia', 'sigla': 'BA', 'regiao': 'Nordeste'},
    '31': {'nome': 'Minas Gerais', 'sigla': 'MG', 'regiao': 'Sudeste'},
    '32': {'nome': 'Espírito Santo', 'sigla': 'ES', 'regiao': 'Sudeste'},
    '33': {'nome': 'Rio de Janeiro', 'sigla': 'RJ', 'regiao': 'Sudeste'},
    '35': {'nome': 'São Paulo', 'sigla': 'SP', 'regiao': 'Sudeste'},
    '41': {'nome': 'Paraná', 'sigla': 'PR', 'regiao': 'Sul'},
    '42': {'nome': 'Santa Catarina', 'sigla': 'SC', 'regiao': 'Sul'},
    '43': {'nome': 'Rio Grande do Sul', 'sigla': 'RS', 'regiao': 'Sul'},
    '50': {'nome': 'Mato Grosso do Sul', 'sigla': 'MS', 'regiao': 'Centro-Oeste'},
    '51': {'nome': 'Mato Grosso', 'sigla': 'MT', 'regiao': 'Centro-Oeste'},
    '52': {'nome': 'Goiás', 'sigla': 'GO', 'regiao': 'Centro-Oeste'},
    '53': {'nome': 'Distrito Federal', 'sigla': 'DF', 'regiao': 'Centro-Oeste'}
}

UF_BY_SIGLA = {v['sigla']: {'code': k, **v} for k, v in UF_MAP.items()}
UF_BY_CODE = UF_MAP

REGIAO_MAP = {
    '1': 'Norte',
    '2': 'Nordeste',
    '3': 'Sudeste',
    '4': 'Sul',
    '5': 'Centro-Oeste'
}

def get_municipality_names(uf_code_or_sigla):
    """
    Fetches official municipality names for a given UF and caches locally.
    """
    cache_path = os.path.join(CACHE_DIR, f"names_mun_{uf_code_or_sigla}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    try:
        url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf_code_or_sigla}/municipios"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            mun_dict = {str(item['id']): item['nome'] for item in r.json()}
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(mun_dict, f, ensure_ascii=False)
            return mun_dict
    except Exception as e:
        print(f"Aviso ao buscar nomes de municípios do IBGE: {e}")
    return {}

def get_mesorregiao_names():
    """
    Fetches official mesorregiões names and metadata from IBGE localidades API.
    """
    cache_path = os.path.join(CACHE_DIR, "names_mesorregioes.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    try:
        url = "https://servicodados.ibge.gov.br/api/v1/localidades/mesorregioes"
        headers = {'User-Agent': 'QGIS-Web-IBGE/1.0'}
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            meso_dict = {}
            for item in r.json():
                mid = str(item['id'])
                uf_obj = item.get('UF', {})
                meso_dict[mid] = {
                    'nome': item.get('nome', f"Mesorregião {mid}"),
                    'sigla_uf': uf_obj.get('sigla', ''),
                    'nm_uf': uf_obj.get('nome', ''),
                    'cd_uf': str(uf_obj.get('id', ''))
                }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(meso_dict, f, ensure_ascii=False)
            return meso_dict
    except Exception as e:
        print(f"Aviso ao buscar nomes de mesorregiões do IBGE: {e}")
    return {}

def fetch_ibge_mesh(mesh_type, uf_code=None):
    """
    Downloads or retrieves cached official IBGE vector mesh in GeoJSON format.
    mesh_type: 'brasil', 'regioes', 'estados', 'mesorregioes', 'municipios'
    uf_code: e.g. 'SP', '35', 'RJ', '33'
    """
    clean_mesh = mesh_type.lower()
    cache_filename = f"mesh_{clean_mesh}"
    if uf_code:
        cache_filename += f"_{uf_code.upper()}"
    cache_filename += ".geojson"
    cache_path = os.path.join(CACHE_DIR, cache_filename)

    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    headers = {'User-Agent': 'QGIS-Web-IBGE/1.0'}
    
    if clean_mesh == 'brasil':
        url = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json"
    elif clean_mesh == 'regioes':
        url = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intrarregiao=regiao"
    elif clean_mesh == 'estados':
        url = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intrarregiao=UF"
    elif clean_mesh in ['mesorregioes', 'mesorregiao', 'meso']:
        if uf_code:
            url = f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf_code}?formato=application/vnd.geo+json&intrarregiao=mesorregiao"
        else:
            url = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intrarregiao=mesorregiao"
    elif clean_mesh == 'mesorregioes_brasil':
        url = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intrarregiao=mesorregiao"
    elif clean_mesh == 'municipios':
        if not uf_code:
            raise ValueError("O código ou sigla da UF é obrigatório para malha de municípios.")
        url = f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf_code}?formato=application/vnd.geo+json&intrarregiao=municipio"
    else:
        raise ValueError(f"Tipo de malha desconhecido: {mesh_type}")

    resp = requests.get(url, headers=headers, timeout=35)
    if resp.status_code != 200:
        raise RuntimeError(f"Erro ao consultar API do IBGE (HTTP {resp.status_code}): {url}")

    geojson_data = resp.json()

    # Enrich features with descriptive properties
    enrich_geojson_properties(geojson_data, clean_mesh, uf_code)

    # Cache locally
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar cache IBGE: {e}")

    return geojson_data

def enrich_geojson_properties(geojson_data, mesh_type, uf_code=None):
    """
    Enriches each feature in the GeoJSON with official names, siglas, and calculated area.
    """
    mun_names = {}
    if mesh_type == 'municipios' and uf_code:
        mun_names = get_municipality_names(uf_code)

    meso_names = {}
    if mesh_type in ['mesorregioes', 'mesorregiao', 'meso', 'mesorregioes_brasil']:
        meso_names = get_mesorregiao_names()

    # Determine UF info if specific UF
    uf_info = None
    if uf_code:
        for cod, data in UF_MAP.items():
            if data['sigla'].upper() == uf_code.upper() or cod == str(uf_code):
                uf_info = data
                break

    for feat in geojson_data.get('features', []):
        props = feat.get('properties', {})
        cod = str(props.get('codarea', ''))

        if mesh_type == 'brasil':
            props['CD_PAIS'] = '076'
            props['NM_PAIS'] = 'Brasil'
            props['SIGLA'] = 'BR'
        elif mesh_type == 'regioes':
            props['CD_REGIAO'] = cod
            props['NM_REGIAO'] = REGIAO_MAP.get(cod, f"Região {cod}")
        elif mesh_type == 'estados':
            info = UF_MAP.get(cod, {})
            props['CD_UF'] = cod
            props['NM_UF'] = info.get('nome', f"Estado {cod}")
            props['SIGLA_UF'] = info.get('sigla', '')
            props['NM_REGIAO'] = info.get('regiao', '')
        elif mesh_type in ['mesorregioes', 'mesorregiao', 'meso', 'mesorregioes_brasil']:
            info = meso_names.get(cod, {})
            props['CD_MESO'] = cod
            props['NM_MESO'] = info.get('nome', f"Mesorregião {cod}")
            if info.get('sigla_uf'):
                props['SIGLA_UF'] = info.get('sigla_uf')
            elif uf_info:
                props['SIGLA_UF'] = uf_info['sigla']
            if info.get('nm_uf'):
                props['NM_UF'] = info.get('nm_uf')
            elif uf_info:
                props['NM_UF'] = uf_info['nome']
        elif mesh_type == 'municipios':
            props['CD_MUN'] = cod
            props['NM_MUN'] = mun_names.get(cod, f"Município {cod}")
            if uf_info:
                props['SIGLA_UF'] = uf_info['sigla']
                props['NM_UF'] = uf_info['nome']

        # Estimate area in km² using shapely geometry
        try:
            geom = shape(feat['geometry'])
            # centroid lat for area estimation
            centroid = geom.centroid
            lat_deg = centroid.y
            cos_lat = math.cos(math.radians(lat_deg))
            # 1 degree lat ~ 111.139 km, 1 degree lon ~ 111.139 * cos(lat) km
            area_deg2 = geom.area
            area_km2 = area_deg2 * (111.139 * 111.139 * cos_lat)
            props['AREA_KM2'] = round(float(area_km2), 2)
        except Exception:
            props['AREA_KM2'] = 0.0

        feat['properties'] = props

def convert_geojson_to_kml(features, layer_name='Camada IBGE'):
    """
    Converts list of GeoJSON features into clean OGC KML with attributes.
    """
    kml = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
    doc = ET.SubElement(kml, 'Document')
    ET.SubElement(doc, 'name').text = layer_name

    for feat in features:
        pm = ET.SubElement(doc, 'Placemark')
        props = feat.get('properties', {})
        name = props.get('NM_MUN') or props.get('NM_UF') or props.get('NM_REGIAO') or props.get('NM_PAIS') or props.get('codarea') or 'Feição'
        ET.SubElement(pm, 'name').text = str(name)

        ext_data = ET.SubElement(pm, 'ExtendedData')
        for k, v in props.items():
            d = ET.SubElement(ext_data, 'Data', name=str(k))
            ET.SubElement(d, 'value').text = str(v)

        geom = feat.get('geometry')
        if not geom:
            continue
        gtype = geom.get('type')
        coords = geom.get('coordinates')

        if gtype == 'Polygon':
            poly = ET.SubElement(pm, 'Polygon')
            outer = ET.SubElement(poly, 'outerBoundaryIs')
            ring = ET.SubElement(outer, 'LinearRing')
            coord_str = ' '.join(f"{c[0]},{c[1]},0" for c in coords[0])
            ET.SubElement(ring, 'coordinates').text = coord_str
        elif gtype == 'MultiPolygon':
            mg = ET.SubElement(pm, 'MultiGeometry')
            for pcoords in coords:
                poly = ET.SubElement(mg, 'Polygon')
                outer = ET.SubElement(poly, 'outerBoundaryIs')
                ring = ET.SubElement(outer, 'LinearRing')
                coord_str = ' '.join(f"{c[0]},{c[1]},0" for c in pcoords[0])
                ET.SubElement(ring, 'coordinates').text = coord_str

    return ET.tostring(kml, encoding='utf-8', xml_declaration=True)

def export_vector(geojson_data, layer_name, format_type='gpkg', target_crs='EPSG:4674'):
    """
    Exports GeoJSON data to GPKG, KML, or GeoJSON with target CRS reprojection.
    Returns: (output_path, download_filename, mimetype)
    """
    fmt = format_type.lower().strip()
    safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in layer_name)

    features = geojson_data.get('features', [])
    if not features:
        raise ValueError("A camada não contém feições para exportação.")

    gdf = gpd.GeoDataFrame.from_features(geojson_data, crs='EPSG:4326')

    # Reproject if needed
    if target_crs and target_crs.upper() != 'EPSG:4326':
        try:
            gdf = gdf.to_crs(target_crs)
        except Exception as e:
            print(f"Aviso ao reprojetar para {target_crs}: {e}")

    if fmt == 'gpkg':
        filename = f"{safe_name}_{target_crs.replace(':', '_')}.gpkg"
        out_path = os.path.join(EXPORTS_DIR, filename)
        if os.path.exists(out_path):
            os.remove(out_path)
        gdf.to_file(out_path, driver='GPKG', layer=safe_name)
        return out_path, filename, 'application/geopackage+sqlite3'

    elif fmt == 'kml':
        filename = f"{safe_name}.kml"
        out_path = os.path.join(EXPORTS_DIR, filename)
        # KML is always WGS84
        if gdf.crs != 'EPSG:4326':
            gdf = gdf.to_crs('EPSG:4326')
        geojson_wgs = json.loads(gdf.to_json())
        kml_bytes = convert_geojson_to_kml(geojson_wgs.get('features', []), layer_name)
        with open(out_path, 'wb') as f:
            f.write(kml_bytes)
        return out_path, filename, 'application/vnd.google-earth.kml+xml'

    elif fmt == 'geojson':
        filename = f"{safe_name}.geojson"
        out_path = os.path.join(EXPORTS_DIR, filename)
        gdf.to_file(out_path, driver='GeoJSON')
        return out_path, filename, 'application/geo+json'

    elif fmt in ('shp', 'shapefile', 'zip'):
        # Export zipped shapefile
        import zipfile
        base_shp = os.path.join(EXPORTS_DIR, safe_name)
        gdf.to_file(base_shp + ".shp")
        zip_filename = f"{safe_name}.zip"
        zip_path = os.path.join(EXPORTS_DIR, zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as z:
            for ext in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
                f = base_shp + ext
                if os.path.exists(f):
                    z.write(f, arcname=safe_name + ext)
                    os.remove(f)
        return zip_path, zip_filename, 'application/zip'
    else:
        raise ValueError(f"Formato de exportação não suportado: {format_type}")
