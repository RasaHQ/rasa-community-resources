import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

NASA_POWER_BASE_URL = os.getenv("NASA_POWER_BASE_URL", "https://power.larc.nasa.gov/api/temporal")
RASA_REST_URL = os.getenv("RASA_REST_URL", "http://localhost:5005")
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache')
