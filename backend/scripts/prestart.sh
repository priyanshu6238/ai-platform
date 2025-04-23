#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python app/backend_pre_start.py

# Run migrations
alembic upgrade head

# Run seed data script
python -m app.seed_data.seed_data

# Initialize services
services=(
    app/initial_data.py
    app/initial_storage.py
)

for i in ${services[@]}; do
    python $i
done
