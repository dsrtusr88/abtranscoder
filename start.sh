#!/bin/bash
echo "Starting script..."

# Display current directory and its contents for debugging
pwd
ls -l

# Run the Python script and capture its output
echo "Running Python script..."
python3 main.py || echo "Python script failed with exit code $?"

echo "Script finished."
