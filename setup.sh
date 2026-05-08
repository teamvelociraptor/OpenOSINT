#!/bin/bash

echo "[*] Installing Python dependencies..."
pip install -r requirements.txt

echo "[*] Installing ExifTool..."
sudo apt install -y libimage-exiftool-perl

echo "[*] Installing PhoneInfoga..."
curl -sSL https://raw.githubusercontent.com/sundowndev/phoneinfoga/master/support/scripts/install.sh | bash
sudo mv ./phoneinfoga /usr/local/bin/

echo "[*] All done."
