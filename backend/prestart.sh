#!/bin/bash

# Let the DB start
python app/backend_pre_start.py

# Run migrations
alembic upgrade head

# Seed the database
python app/db/seed_data.py  # This runs the seeding process

# Create initial data in DB
python app/initial_data.py
