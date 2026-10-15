#!/usr/bin/env python3
"""
Script de construção do DivinoGIS Portable para Windows 64-bit.
Monta uma distribuição 100% autocontida que roda direto do pendrive
sem necessidade de instalação nem privilégios de administrador.
"""

import os
import sys
import shutil
import zipfile
import glob
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WHEELS_CACHE = Path("/tmp/win_pack_test")
OUTPUT_BASE = BASE_DIR / "dist"
DIST_DIR = OUTPUT_BASE / "DivinoGIS_Portable_Win64"
RUNTIME_DIR = DIST_DIR / "runtime"
SITE_PACKAGES_DIR = RUNTIME_DIR / "Lib" / "site-packages"
FINAL_ZIP = BASE_DIR / "DivinoGIS_Portable_Win64.zip"

def main():
    print("=" * 60)
    print("  Construindo DivinoGIS Portable (Windows 64-bit)")
    print("=" * 60)

    # 1. Prepara diretórios de dados e runtime
    (DIST_DIR / "data_cache" / "hgt").mkdir(parents=True, exist_ok=True)
    (DIST_DIR / "data_cache" / "ibge").mkdir(parents=True, exist_ok=True)
    (DIST_DIR / "exports").mkdir(parents=True, exist_ok=True)

    runtime_exists = (RUNTIME_DIR / "python.exe").exists() and (SITE_PACKAGES_DIR).exists()
    
    if not runtime_exists:
        SITE_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
        # 2. Extrai Python Embeddable 3.11.9
        embed_zip = WHEELS_CACHE / "python-3.11.9-embed-amd64.zip"
        if not embed_zip.exists():
            print(f"ERRO: {embed_zip} não encontrado!")
            sys.exit(1)
            
        print(f"-> Extraindo Python 3.11.9 Embeddable para: {RUNTIME_DIR}")
        with zipfile.ZipFile(embed_zip, 'r') as z:
            z.extractall(RUNTIME_DIR)

        # 3. Extrai todas as Wheels para Lib/site-packages
        wheels = sorted(glob.glob(str(WHEELS_CACHE / "*.whl")))
        print(f"-> Extraindo {len(wheels)} bibliotecas (wheels Windows x64) para site-packages...")
        
        msvcp140_found = None
        for whl in wheels:
            whl_name = Path(whl).name
            print(f"   [+] {whl_name}")
            with zipfile.ZipFile(whl, 'r') as z:
                for member in z.infolist():
                    if "__pycache__" in member.filename:
                        continue
                    z.extract(member, SITE_PACKAGES_DIR)
                    if "msvcp140" in member.filename.lower() and member.filename.lower().endswith(".dll"):
                        msvcp140_found = SITE_PACKAGES_DIR / member.filename

        if msvcp140_found and msvcp140_found.exists():
            print(f"-> Instalando DLL msvcp140.dll em {RUNTIME_DIR}...")
            shutil.copy2(msvcp140_found, RUNTIME_DIR / "msvcp140.dll")
    else:
        print("-> Runtime Python 3.11.9 Embeddable e bibliotecas Windows x64 existentes detectados. Reutilizando...")

    # 4. Configura python311._pth para carregar site-packages e a raiz da aplicação
    pth_file = RUNTIME_DIR / "python311._pth"
    pth_content = (
        "python311.zip\n"
        ".\n"
        "Lib\\site-packages\n"
        "..\\\n"
        "import site\n"
    )
    print("-> Configurando python311._pth com suporte a site-packages e diretório raiz...")
    pth_file.write_text(pth_content, encoding="utf-8")

    # 5. Copia arquivos da aplicação
    print("-> Copiando código-fonte e recursos estáticos do DivinoGIS...")
    app_files = [
        "app.py",
        "net_utils.py",
        "srtm_service.py",
        "ibge_service.py",
        "stl_service.py",
        "LICENSE",
        "PROJECT_CONTEXT.md"
    ]
    for af in app_files:
        src = BASE_DIR / af
        if src.exists():
            shutil.copy2(src, DIST_DIR / af)

    # Copia pastas estáticas e templates
    shutil.copytree(BASE_DIR / "templates", DIST_DIR / "templates", dirs_exist_ok=True)
    shutil.copytree(BASE_DIR / "static", DIST_DIR / "static", dirs_exist_ok=True)

    # Cria arquivos .gitkeep nas pastas de cache e exportação
    (DIST_DIR / "data_cache" / "hgt" / ".gitkeep").touch()
    (DIST_DIR / "data_cache" / "ibge" / ".gitkeep").touch()
    (DIST_DIR / "exports" / ".gitkeep").touch()

    # 6. Cria os inicializadores para Windows (.bat e .vbs)
    print("-> Criando scripts de inicialização para Windows...")
    
    bat_content = r"""@echo off
chcp 65001 >nul
title DivinoGIS - SIG Topográfico 3D & Malhas IBGE
cd /d "%~dp0"

echo =====================================================================
echo           DIVINOGIS PORTABLE (Windows 64-bit)
echo =====================================================================
echo.
echo   * Iniciando motor Python e bibliotecas espaciais (GDAL/PROJ)...
echo   * Nenhuma instalacao necessaria no computador.
echo   * Para fechar, basta fechar esta janela preta ou executar 'Encerrar.bat'.
echo.
echo =====================================================================
echo.

:: Define caminhos de busca para PROJ, GDAL e Certificados SSL
set "PYTHONHOME=%~dp0runtime"
set "PYTHONPATH=%~dp0;%~dp0runtime\Lib\site-packages"
set "PROJ_LIB=%~dp0runtime\Lib\site-packages\pyproj\proj_dir\share\proj"
set "GDAL_DATA=%~dp0runtime\Lib\site-packages\rasterio\gdal_data"
set "SSL_CERT_FILE=%~dp0runtime\Lib\site-packages\certifi\cacert.pem"
set "REQUESTS_CA_BUNDLE=%~dp0runtime\Lib\site-packages\certifi\cacert.pem"
set "CURL_CA_BUNDLE=%~dp0runtime\Lib\site-packages\certifi\cacert.pem"
set "PORT=5001"

:: Abre o navegador padrao apos 2 segundos
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5001"

:: Inicia o servidor Flask com o interpretador embutido
"%~dp0runtime\python.exe" app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] O servidor foi encerrado com codigo de erro %ERRORLEVEL%.
    pause
)
"""
    (DIST_DIR / "DivinoGIS.bat").write_text(bat_content, encoding="utf-8")
    (DIST_DIR / "Iniciar_DivinoGIS.bat").write_text(bat_content, encoding="utf-8")

    vbs_content = r"""Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "DivinoGIS.bat" & Chr(34), 0
Set WshShell = Nothing
"""
    (DIST_DIR / "Iniciar_Silencioso.vbs").write_text(vbs_content, encoding="utf-8")

    stop_bat = r"""@echo off
chcp 65001 >nul
title Encerrando DivinoGIS
cd /d "%~dp0"

echo Encerrando instancias do DivinoGIS...
taskkill /f /im python.exe /fi "WINDOWTITLE eq DivinoGIS*" 2>nul
echo Concluido. O sistema foi finalizado.
timeout /t 2 /nobreak >nul
"""
    (DIST_DIR / "Encerrar_DivinoGIS.bat").write_text(stop_bat, encoding="utf-8")

    readme_content = r"""================================================================================
                    DIVINOGIS PORTABLE (WINDOWS 64-BIT)
================================================================================

Este pacote é 100% portátil e autossuficiente:
- Não precisa de Python instalado na máquina.
- Não precisa de permissões de Administrador.
- Pode ser copiado e executado diretamente a partir de um PENDRIVE ou HD Externo.

--------------------------------------------------------------------------------
COMO USAR NO PENDRIVE:
--------------------------------------------------------------------------------
1. Copie esta pasta inteira ("DivinoGIS_Portable_Win64") para dentro do seu pendrive.
2. No computador com Windows (qualquer Windows 10 ou 11 de 64 bits), abra a pasta.
3. Dê DOIS CLIQUES em:
   👉 "DivinoGIS.bat"  (ou "Iniciar_DivinoGIS.bat")

4. Uma tela preta se abrirá e, em 2 segundos, o seu navegador de internet padrão 
   (Chrome, Edge, Firefox, Brave, etc.) abrirá automaticamente no endereço:
   👉 http://localhost:5001

5. Pronto! O DivinoGIS estará pronto para uso:
   - Baixar e recortar relevos SRTM 30m por área (AOI) ou feição vetorial selecionada.
   - Carregar malhas oficiais do IBGE (UFs, Mesorregiões, Municípios).
   - Exportar dados em GeoPackage (.gpkg), KML (.kml), GeoJSON e Shapefile (.shp).
   - Visualizar em 3D e exportar malhas sólidas (.stl) prontas para impressão 3D.

--------------------------------------------------------------------------------
COMO ENCERRAR:
--------------------------------------------------------------------------------
- Basta fechar a janela preta do console ou dar dois cliques em "Encerrar_DivinoGIS.bat".
- Nenhum arquivo ou registro é deixado no computador hospedeiro.

--------------------------------------------------------------------------------
DICA:
--------------------------------------------------------------------------------
- Se você não quiser que a janela preta do console fique visível na barra de tarefas, 
  você pode iniciar dando dois cliques em "Iniciar_Silencioso.vbs".
================================================================================
"""
    (DIST_DIR / "COMO_USAR_NO_PENDRIVE.txt").write_text(readme_content, encoding="utf-8")

    # 7. Gera o arquivo compactado .ZIP final
    if FINAL_ZIP.exists():
        FINAL_ZIP.unlink()

    print(f"-> Compactando pasta em '{FINAL_ZIP.name}' para transporte fácil no pendrive...")
    shutil.make_archive(
        base_name=str(BASE_DIR / "DivinoGIS_Portable_Win64"),
        format='zip',
        root_dir=str(OUTPUT_BASE),
        base_dir="DivinoGIS_Portable_Win64"
    )

    zip_size_mb = FINAL_ZIP.stat().st_size / (1024 * 1024)
    print("=" * 60)
    print(f"  SUCESSO! Pacote portátil gerado com êxito!")
    print(f"  Arquivo final: {FINAL_ZIP}")
    print(f"  Tamanho do ZIP: {zip_size_mb:.2f} MB")
    print("=" * 60)

if __name__ == "__main__":
    main()
