#!/bin/bash

# Set permissions for /config
chown -R nobody:nobody /config

# Execute the main.py script
su -s /bin/bash nobody <<EOF
python app/main.py
EOF
