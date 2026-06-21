import os
from pathlib import Path
from datetime import timedelta
import environ
import sys
from celery.schedules import crontab
# Initialize environment variables
env = environ.Env()
environ.Env.read_env()

# Base directory
BASE_DIR = Path(__file__).parents[2]


# Secret key (should be overridden in production)
SECRET_KEY = env("SECRET_KEY")

# Installed apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 3rd party
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    "rest_framework_simplejwt.token_blacklist",
    'django_cleanup',
    'django_celery_results',
    'django_filters',
    'django_celery_beat',
    'silk',
    'django_extensions',
    # Custom apps
    'account',
    'club',
    'core',
    'member',
    'activity_log',
    'event',
    'product',
    'restaurant',
    'member_financial_management',
    'facility',
    'promo_code_app',
    'mails',
    'dashboard',
    'attendance',
    'outlet',
    'reservation',
    'payroll',
    'vendor',
    'finance_core',
]

# Middleware
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # 3rd party
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'silk.middleware.SilkyMiddleware',
    # Custom
    'account.middleware.JWTMiddleware',
    'core.middleware.MaxUploadSizeMiddleware',
]

# URL & WSGI
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

# Password Validators
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Language & Timezone
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'  # Use local timezone
USE_I18N = True
USE_TZ = True

# Static & Media files
STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default auto field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication
AUTH_USER_MODEL = 'account.CustomUser'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'EXCEPTION_HANDLER': 'account.utils.exceptions.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',  # Throttles per user
        # Throttles for unauthenticated users
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '80/minute',  # Limit to 80 requests per minute for authenticated users
        'anon': '60/minute',  # Limit to 60 requests per minute for anonymous users
    }
}

# JWT Configuration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),  # Short-lived access token
    # Refresh token valid for 15 days
    "REFRESH_TOKEN_LIFETIME": timedelta(days=15),
    "ROTATE_REFRESH_TOKENS": True,  # Generates new refresh tokens on every refresh
    "BLACKLIST_AFTER_ROTATION": True,  # Old refresh tokens become invalid
    "ALGORITHM": "HS256",  # Secure hashing algorithm
    "SIGNING_KEY": env("SECRET_KEY"),  # Use Django's SECRET_KEY to sign JWTs
    "AUTH_HEADER_TYPES": ("Bearer",),  # JWTs can still be passed in headers
    "AUTH_COOKIE": "access_token",  # Name of the cookie storing the access token
    # Name of the cookie storing the refresh token
    "AUTH_COOKIE_REFRESH": "refresh_token",
    "AUTH_COOKIE_HTTP_ONLY": True,  # Prevent JavaScript from accessing cookies
    # Send cookies only over HTTPS (for production)
    "AUTH_COOKIE_SECURE": env.bool("COOKIE_SECURE", default=False),
}

# Celery settings
result_backend = 'django-db'
accept_content = ['json']
task_serializer = 'json'
result_serializer = 'json'
timezone = 'Asia/Dhaka'
CELERY_TASK_REJECT_ON_WORKER_LOST = True

DJANGO_ENV = os.getenv("DJANGO_ENV", default="development")
if DJANGO_ENV == "production":
    REDIS_LOCATION = os.getenv("REDIS_URL_PROD")
else:
    REDIS_LOCATION = os.getenv("REDIS_URL_DEV")

CELERY_BROKER_URL = REDIS_LOCATION


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_LOCATION,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "COMPRESSOR_OPTIONS": {
                "min_length": 1024
            },
            "IGNORE_EXCEPTIONS": True,
        }
    }
}

# Create logs directory if not exists
LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024      # 50MB per file
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024      # 50MB total per request


### LOGGER settings ###
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/debug.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'myapp': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# template settings
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Look for templates in 'templates' folder
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env("EMAIL_HOST_USER")

if 'test' in sys.argv:
    # Disable throttling in tests
    REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # Collected files


CELERY_BEAT_SCHEDULE = {
    "flush-activity-logs-every-10-min": {
        "task": "activity_log.tasks.flush_activity_logs",
        "schedule": crontab(minute="*/10"),
    },
    "delete-expired-activity-logs-daily": {
        "task": "activity_log.tasks.delete_expired_activity_logs",
        "schedule": crontab(minute=0, hour=0),  # Runs every day at 00:00

    },
}
