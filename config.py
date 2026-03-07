from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_IDS = [int(elem.strip()) for elem in os.getenv("ALLOWED_IDS", "").split(",") if elem]