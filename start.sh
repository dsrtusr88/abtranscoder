#!/bin/bash

# Set the umask to allow group write permissions
umask 0002

# Set the permissions of the script to 777
chmod 777 start.sh

# Execute the main.py script
python main.py
