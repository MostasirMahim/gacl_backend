#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    import environ
    from pathlib import Path

    # Load .env file from config/settings folder so DJANGO_ENV is available
    env_path = Path(__file__).parent / "config" / "settings" / ".env"
    if env_path.exists():
        environ.Env.read_env(str(env_path))

    DJANGO_ENV = os.getenv('DJANGO_ENV', 'development')
    if DJANGO_ENV == 'production':
        os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                              'config.settings.production')
    else:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                              'config.settings.development')

    # os.environ.setdefault('DJANGO_SETTINGS_MODULE',
    #                       'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
