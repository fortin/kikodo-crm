#!/bin/bash
# Installation script for Python 3.13 compatibility
# This ensures setuptools is installed before other packages that may need to build from source

echo "Installing base requirements (setuptools, wheel, pip)..."
pip install -r requirements-base.txt

echo "Installing main requirements..."
pip install -r requirements.txt

echo "Installation complete!"
