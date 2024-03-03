#!/bin/bash

# Ensure script exits on failure
set -e

# Execute the Python script and log errors
python3 main.py 2>&1 | tee /app/log.txt
