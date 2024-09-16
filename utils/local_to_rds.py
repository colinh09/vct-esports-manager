import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def connect_to_db(connection_string):
    return psycopg2.connect(connection_string)

def get_table_names(cursor):
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
    """)
    return [row[0] for row in cursor.fetchall()]

def get_table_schema(cursor, table_name):
    cursor.execute(sql.SQL("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = {}
    """).format(sql.Literal(table_name)))
    return cursor.fetchall()

def create_table(cursor, table_name, schema):
    columns = [f"{col} {dtype}" for col, dtype in schema]
    create_query = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
        sql.Identifier(table_name),
        sql.SQL(', ').join(map(sql.SQL, columns))
    )
    cursor.execute(create_query)

def table_exists(cursor, table_name):
    cursor.execute(sql.SQL("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = {}
        )
    """).format(sql.Literal(table_name)))
    return cursor.fetchone()[0]

def copy_table(source_cursor, dest_cursor, table_name, batch_size=10000):
    # Get column names
    source_cursor.execute(sql.SQL("SELECT * FROM {} LIMIT 0").format(sql.Identifier(table_name)))
    columns = [desc[0] for desc in source_cursor.description]
    
    # Prepare insert query
    insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table_name),
        sql.SQL(', ').join(map(sql.Identifier, columns)),
        sql.SQL(', ').join(sql.Placeholder() * len(columns))
    )
    
    # Fetch and insert data in batches
    source_cursor.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name)))
    
    batch = source_cursor.fetchmany(batch_size)
    total_rows = 0
    
    while batch:
        try:
            dest_cursor.executemany(insert_query, batch)
            total_rows += len(batch)
            logging.info(f"Inserted batch of {len(batch)} rows into {table_name}. Total rows: {total_rows}")
        except Exception as e:
            logging.error(f"Error inserting batch into {table_name}: {e}")
        
        batch = source_cursor.fetchmany(batch_size)
    
    logging.info(f"Finished copying {total_rows} rows into {table_name}")

def main():
    # Get environment variables
    source_connection_string = os.getenv('DATABASE_URL')
    master_password = os.getenv('MASTER_PASSWORD')
    rds_name = os.getenv('RDS_NAME')

    # Log debug information
    logging.info(f"Source connection string: {source_connection_string}")
    logging.info(f"RDS Name: {rds_name}")
    logging.info(f"Master password is set: {'Yes' if master_password else 'No'}")

    # Construct destination connection string
    dest_connection_string = f"postgresql://postgres:{master_password}@{rds_name}:5432/vct-manager"
    logging.info(f"Destination connection string: {dest_connection_string}")

    # Connect to source database
    try:
        source_conn = connect_to_db(source_connection_string)
        source_cursor = source_conn.cursor()
        logging.info("Successfully connected to source database")
    except Exception as e:
        logging.error(f"Error connecting to source database: {e}")
        return

    # Connect to destination database
    try:
        dest_conn = connect_to_db(dest_connection_string)
        dest_cursor = dest_conn.cursor()
        logging.info("Successfully connected to destination database")
    except Exception as e:
        logging.error(f"Error connecting to destination database: {e}")
        return

    try:
        # Get table names from source database
        source_tables = get_table_names(source_cursor)
        logging.info(f"Found {len(source_tables)} tables in source database")

        # Identify tables that don't exist in the destination database
        tables_to_create = [table for table in source_tables if not table_exists(dest_cursor, table)]
        logging.info(f"{len(tables_to_create)} out of {len(source_tables)} tables need to be created in destination database")

        # Copy each table
        for table in tables_to_create:
            logging.info(f"Processing table: {table}")
            
            # Get table schema
            schema = get_table_schema(source_cursor, table)
            
            if table in tables_to_create:
                logging.info(f"Creating table '{table}' in destination database")
                create_table(dest_cursor, table, schema)
            
            # Copy data
            copy_table(source_cursor, dest_cursor, table)
            dest_conn.commit()
            logging.info(f"Finished copying table: {table}")

        logging.info("Migration completed successfully!")

    except Exception as e:
        logging.error(f"An error occurred during migration: {e}")
        dest_conn.rollback()

    finally:
        source_cursor.close()
        source_conn.close()
        dest_cursor.close()
        dest_conn.close()
        logging.info("Database connections closed")

if __name__ == "__main__":
    main()