import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hospital.settings")

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()
