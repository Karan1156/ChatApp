#!/bin/bash
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Apply existing migrations (DO NOT create new ones)
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput