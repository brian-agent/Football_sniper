import os
from django.core.wsgi import get_wsgi_application

# Tell Django to use core/settings.py
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# Create the WSGI application object for Gunicorn
application = get_wsgi_application()