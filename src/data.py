import pyspark
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

def get_spark_session():
    return SparkSession.builder \
        .appName("ValorantEsportsManager") \
        .config("spark.driver.memory", "4g") \
        .config("spark.executor.memory", "4g") \
        .getOrCreate()

def get_data():
    spark = get_spark_session()
    # Read the JSON file as a single column DataFrame
    raw_df = spark.read.json('data/sample.json', multiLine=True)
    
    # Define the list of event types
    event_types = [
        "abilityUsed", "configuration", "damageEvent", "gameDecided", "gamePhase",
        "inventoryTransaction", "metadata", "observerTarget", "platformGameId",
        "playerDied", "playerSpawn", "roundCeremony", "roundDecided", "roundEnded",
        "roundStarted", "snapshot", "spikeDefuseCheckpointReached", "spikeDefuseStarted",
        "spikeDefuseStopped", "spikePlantCompleted", "spikePlantStarted", "spikePlantStopped",
        "spikeStatus"
    ]
    
    # Create columns for each event type
    for event_type in event_types:
        raw_df = raw_df.withColumn(event_type, col(event_type))
    
    # Select all the event type columns
    df = raw_df.select(*event_types)
    
    return df

def get_column_counts(df):
    for col_name in df.columns:
        # Count non-null values in each column
        non_null_count = df.select(col_name).na.drop().count()
        print(f"Column: {col_name}, Non-null Count: {non_null_count}")

def print_first_20_rows(df):
    # Convert to Pandas DataFrame for easier printing
    pandas_df = df.limit(20).toPandas()
    
    # Print each row
    for index, row in pandas_df.iterrows():
        print(f"\nRow {index + 1}:")
        for column in pandas_df.columns:
            value = row[column]
            if value is not None:
                print(f"  {column}: {value}")

# Main execution
df = get_data()  # Load your data
get_column_counts(df)  # Get counts of each column
print("\nFirst 20 rows of the DataFrame:")
print_first_20_rows(df)