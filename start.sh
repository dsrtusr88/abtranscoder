#!/bin/bash

echo "Starting application..."

# Displaying current directory and its content for debugging
echo "Current working directory: $(pwd)"
ls -lah

# Running the Python script
python /app/main.py

echo "Application has stopped."
