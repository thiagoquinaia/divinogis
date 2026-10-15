import os
import requests
import certifi
import urllib3

# Suprime avisos de requisições inseguras quando houver fallback SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configura variáveis globais de certificados para Python e bibliotecas C
try:
    ca_bundle = certifi.where()
    if os.path.exists(ca_bundle):
        os.environ.setdefault('SSL_CERT_FILE', ca_bundle)
        os.environ.setdefault('REQUESTS_CA_BUNDLE', ca_bundle)
        os.environ.setdefault('CURL_CA_BUNDLE', ca_bundle)
except Exception:
    ca_bundle = True

def safe_get(url, **kwargs):
    """
    Executa requests.get garantindo suporte a certificados SSL.
    Se a verificação estrita falhar (típico em ambientes Windows portáteis
    sem cadeia de certificados de raiz ou com intermediários governamentais/ICP-Brasil),
    executa fallback automático com verify=False para assegurar a continuidade do serviço.
    """
    kwargs.setdefault('verify', ca_bundle)
    try:
        return requests.get(url, **kwargs)
    except requests.exceptions.SSLError:
        kwargs['verify'] = False
        return requests.get(url, **kwargs)
