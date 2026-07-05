from .base import *
import pdb

# Debug mode OFF for production
DEBUG = False

# celery settings

# Production settings
SILKY_PYTHON_PROFILER = False
SILKY_PYTHON_PROFILER_BINARY = False
SILKY_META = False

# Define production hosts
ALLOWED_HOSTS = ["*"]

# # Use PostgreSQL in production

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env("DB_NAME"),
        'USER': env("DB_USER"),
        'PASSWORD': env("DB_PASSWORD"),
        'HOST': env("DB_HOST"),
        'PORT': env("DB_PORT"),
    }
}
# local database for testing
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',  # Main DB
#     }
# }

# Email settings for production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env("EMAIL_HOST", default='smtp.gmail.com')
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default='')
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default='')

# CORS settings for production
# CORS_ALLOWED_ORIGINS = []
# CORS for local development
CORS_ORIGIN_ALLOW_ALL = True
# Cookie security OFF for development
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CORS_ALLOW_CREDENTIALS = True


print("Using production settings")
