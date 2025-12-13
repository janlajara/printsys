#!/bin/bash
set -e
gunicorn printsys.wsgi --log-file -