#!/bin/bash
set -e
python manage.py migrate
python manage.py makesuperuser
python manage.py loaddata fixtures/stockmovementpurpose.json
python manage.py loaddata fixtures/itemcategory.json
python manage.py loaddata fixtures/item.json