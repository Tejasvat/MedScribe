#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "==> Updating package installer..."
python -m pip install --upgrade pip setuptools wheel

echo "==> Installing MediScribe dependencies..."
pip install -r requirements.txt

echo "==> Installing package in editable mode..."
pip install -e .

echo "==> Build completed successfully!"
