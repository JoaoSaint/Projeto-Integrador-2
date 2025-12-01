import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests

# Coordenadas fixas da cidade (placeholder)
# Exemplo: São Paulo → latitude=-23.55, longitude=-46.63
LATITUDE = -21.3607
LONGITUDE = -48.2282

# Data de interesse (placeholder no formato AAAA-MM-DD)
DATA = "2025-10-05"

# Endpoint da Open-Meteo para dados históricos
url = (
    "https://archive-api.open-meteo.com/v1/archive"
    f"?latitude={LATITUDE}"
    f"&longitude={LONGITUDE}"
    f"&start_date={DATA}"
    f"&end_date={DATA}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"
    "&timezone=America/Sao_Paulo"
)

# Fazendo a requisição
resposta = requests.get(url)

dados = resposta.json()
d = dados['daily']

print("Dados meteorológicos do dia:", DATA)
print(f"Data: {d['time'][0]}")
print(f"Temperatura máxima: {d['temperature_2m_max'][0]} °C")
print(f"Temperatura mínima: {d['temperature_2m_min'][0]} °C")
print(f"Precipitação total: {d['precipitation_sum'][0]} mm")
print(f"Vento máximo: {d['wind_speed_10m_max'][0]} km/h")