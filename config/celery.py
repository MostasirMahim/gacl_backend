import os
import environ
from pathlib import Path

from celery import Celery
from django.conf import settings

# Load .env file from settings folder so DJANGO_ENV is available
env_path = Path(__file__).parent / "settings" / ".env"
if env_path.exists():
    environ.Env.read_env(str(env_path))

DJANGO_ENV = os.getenv('DJANGO_ENV', 'development')
if DJANGO_ENV == 'production':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'config.settings.production')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'config.settings.development')
app = Celery('config')
app.conf.update(timezone='Asia/Dhaka')
app.config_from_object(settings, namespace='CELERY')

# For Autodiscover tasks
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
