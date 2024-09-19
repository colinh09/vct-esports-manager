import pyspark 
from pyspark.sql import SparkSession

def get_spark_session():
    return SparkSession.builder \
        .appName("ValorantEsportsManager") \
        .config("spark.driver.memory", "4g") \
        .config("spark.executor.memory", "4g") \
        .getOrCreate()


def get_data():
    spark = get_spark_session()
    df = spark.read.json('data/sample.json')
    df.printSchema()
    return df



def get_column_counts(df):
    for col_name in df.columns:
        # Count non-null values in each column
        non_null_count = df.select(col_name).na.drop().count()
        print(f"Column: {col_name}, Non-null Count: {non_null_count}")

df = get_data()  # Load your data
get_column_counts(df)  # Get counts of each column

