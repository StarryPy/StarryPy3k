#!/bin/bash

# If we run in docker, and the user chose a file share volume, these files won't exist. Starry will complain.
# Rather than change the way starry does its default files, let's just ensure they are present with this shell script.
if [ -f /app/config/config.json.default ]; then
    cp /app/defaults/config.json.default /app/config
fi

if [ -f /app/config/permissions.json.default ]; then
    cp /app/defaults/permissions.json.default /app/config
fi

python3 ./server.py