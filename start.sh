#!/bin/bash
cd ~/kudi-arc
source kudi-env/bin/activate
exec gunicorn -c gunicorn.conf.py app:app
