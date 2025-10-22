# weaviate_client.py
import os
import weaviate
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

# Prioritet: WEAVIATE_URL (npr. http://localhost:8080), fallback na scheme/host/port
weaviate_url = os.getenv("WEAVIATE_URL")
if weaviate_url:
    p = urlparse(weaviate_url)
    scheme = p.scheme or "http"
    host = p.hostname or "localhost"
    port = str(p.port or 8080)
else:
    scheme = os.getenv("WEAVIATE_SCHEME", "http")
    host = os.getenv("WEAVIATE_HOST", "localhost")
    port = os.getenv("WEAVIATE_PORT", "8080")

api_key = os.getenv("WEAVIATE_API_KEY")
url = f"{scheme}://{host}:{port}"

if api_key:
    auth = weaviate.auth.AuthApiKey(api_key=api_key)
    WVT = weaviate.Client(url, auth_client_secret=auth)
else:
    WVT = weaviate.Client(url)
