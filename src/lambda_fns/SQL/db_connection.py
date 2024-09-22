import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    # db_url = os.environ['RDS_DATABASE_URL']
    db_url='postgresql://postgres:lJFiUe0eQ9ABnCbvGzA4@vct-manager.cf2yk22m4o7w.us-east-1.rds.amazonaws.com:5432/vct-manager'
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)