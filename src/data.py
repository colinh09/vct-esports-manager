import pyspark
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, ArrayType, MapType

def get_spark_session():
    return SparkSession.builder \
        .appName("ValorantEsportsManager") \
        .config("spark.driver.memory", "4g") \
        .config("spark.executor.memory", "4g") \
        .getOrCreate()

def get_data():
    spark = get_spark_session()
    raw_df = spark.read.json('../data/test-files/sample/sample.json', multiLine=True)
    return raw_df

def print_schema_recursively(schema, level=0, file=None):
    for field in schema.fields:
        indent = "  " * level
        field_info = f"{indent}- {field.name}: {field.dataType}"
        print(field_info)
        if file:
            file.write(field_info + "\n")
        
        if isinstance(field.dataType, StructType):
            print_schema_recursively(field.dataType, level + 1, file)
        elif isinstance(field.dataType, ArrayType):
            element_type = field.dataType.elementType
            array_info = f"{indent}  [Array of {element_type}]:"
            print(array_info)
            if file:
                file.write(array_info + "\n")
            if isinstance(element_type, StructType):
                print_schema_recursively(element_type, level + 2, file)
        elif isinstance(field.dataType, MapType):
            map_info = f"{indent}  {{Map}}: key_type: {field.dataType.keyType}, value_type: {field.dataType.valueType}"
            print(map_info)
            if file:
                file.write(map_info + "\n")

def expand_struct_type(struct_type, level=0):
    indent = "  " * level
    result = "{\n"
    for field in struct_type.fields:
        result += f"{indent}  \"{field.name}\": "
        if isinstance(field.dataType, StructType):
            result += expand_struct_type(field.dataType, level + 1)
        elif isinstance(field.dataType, ArrayType):
            result += f"[Array of {field.dataType.elementType}]"
            if isinstance(field.dataType.elementType, StructType):
                result += " " + expand_struct_type(field.dataType.elementType, level + 1)
        elif isinstance(field.dataType, MapType):
            result += f"{{Map}} key_type: {field.dataType.keyType}, value_type: {field.dataType.valueType}"
        else:
            result += str(field.dataType)
        result += ",\n"
    result = result.rstrip(",\n") + "\n" + indent + "}"
    return result

def analyze_json_structure(df):
    schema = df.schema
    
    with open("json_structure.txt", "w") as file:
        file.write("JSON Structure:\n")
        for field in schema.fields:
            field_info = f"- {field.name}: "
            if isinstance(field.dataType, StructType):
                field_info += expand_struct_type(field.dataType)
            elif isinstance(field.dataType, ArrayType):
                field_info += f"[Array of {field.dataType.elementType}]"
                if isinstance(field.dataType.elementType, StructType):
                    field_info += " " + expand_struct_type(field.dataType.elementType)
            elif isinstance(field.dataType, MapType):
                field_info += f"{{Map}} key_type: {field.dataType.keyType}, value_type: {field.dataType.valueType}"
            else:
                field_info += str(field.dataType)
            file.write(field_info + "\n\n")
        print(f"JSON structure has been written to json_structure.txt")

def get_column_counts(df):
    for col_name in df.columns:
        non_null_count = df.select(col_name).na.drop().count()
        print(f"Column: {col_name}, Non-null Count: {non_null_count}")

# Main execution
df = get_data()  # Load your data
analyze_json_structure(df)  # Analyze and print the JSON structure to file
get_column_counts(df)  # Get counts of each column