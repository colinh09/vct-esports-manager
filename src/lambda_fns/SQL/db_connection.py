import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    db_url = os.environ['RDS_DATABASE_URL']
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)