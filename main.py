import os

import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Fetch variables
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing in environment")

# Connect to the database
connection = psycopg2.connect(DATABASE_URL)

with connection.cursor() as cursor:
    cursor.execute("SELECT 1")
    print("Database connection OK:", cursor.fetchone()[0])

connection.close()
