#!/bin/bash
if [ "$1" != "mexc" ]; then
    echo "Usage: bash install.sh mexc"
    exit 1
fi
echo "--- Installation MEXC ---"
sudo apt-get update -y
sudo apt-get install python3-venv -y
if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install ccxt==4.4.7 pydantic==2.5.3 pandas==2.2.0 ta==0.11.0
echo "Installation terminée."
