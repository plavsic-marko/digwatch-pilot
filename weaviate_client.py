# weaviate_client.py
import os
import weaviate
from dotenv import load_dotenv

# Učitaj .env varijable
load_dotenv()

# Čitanje iz .env (sa default vrednostima)
scheme = os.getenv("WEAVIATE_SCHEME", "http")
host = os.getenv("WEAVIATE_HOST", "localhost")
port = os.getenv("WEAVIATE_PORT", "8080")
api_key = os.getenv("WEAVIATE_API_KEY")

url = f"{scheme}://{host}:{port}"

# Inicijalizacija klijenta
if api_key:
    auth = weaviate.auth.AuthApiKey(api_key=api_key)
    WVT = weaviate.Client(url, auth_client_secret=auth)
else:
    WVT = weaviate.Client(url)
