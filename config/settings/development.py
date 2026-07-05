from .base import *
import os
# Debug mode ON for development
DEBUG = True
# Production settings
SILKY_PYTHON_PROFILER = False
SILKY_PYTHON_PROFILER_BINARY = False
SILKY_PYTHON_PROFILER_RESULT_PATH = os.path.join(MEDIA_ROOT, 'silk-profiles')
os.makedirs(SILKY_PYTHON_PROFILER_RESULT_PATH, exist_ok=True)
# Allow all hosts
ALLOWED_HOSTS = ["*"]


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # Main DB
    }
    # ,
    # 'secondary': {
    #     'ENGINE': 'django.db.backends.sqlite3',
    #     'NAME': BASE_DIR / 'secondary_db.sqlite3',  # Secondary DB
    # }
}

# DATABASE_ROUTERS = ['core.db_router.SecondaryRouter']



# Email settings (use console backend for development)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env("EMAIL_HOST", default='smtp.gmail.com')
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default='')
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default='')


# CORS for local development
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True

# Cookie security OFF for development
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"].append(
    "rest_framework.authentication.SessionAuthentication")


print("Using development settings")

# Run Celery tasks synchronously in development when no broker is available,
# so activity-log / notification tasks don't fail on a missing Redis.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False
