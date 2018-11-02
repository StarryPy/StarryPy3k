#!/bin/bash

# If we run in docker, and the user chose a file share volume, these files won't exist. Starry will complain.
# Rather than change the way starry does its default files, let's just ensure they are present with this shell script.
if [ ! -f config/config.json.default ]; then
    cp defaults/config.json.default config
fi

if [ ! -f config/permissions.json.default ]; then
    cp defaults/permissions.json.default config
fi

python3 ./server.py