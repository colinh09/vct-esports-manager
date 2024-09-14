import boto3
import os
import json

def create_or_update_lambda():
    # Initialize AWS client
    lambda_client = boto3.client('lambda')

    # Get user input
    function_name = input("Enter the name for your Lambda function: ").strip()
    default_arn = "arn:aws:iam::423623863958:role/service-role/SQL-role-jhv0ar4d"
    role_arn = input(f"Enter the ARN of the IAM role for the Lambda function (press Enter for default: {default_arn}): ").strip()
    if not role_arn:
        role_arn = default_arn
    handler = input("Enter the handler (e.g., lambda_function.lambda_handler): ").strip()
    runtime = input("Enter the runtime (e.g., python3.10): ").strip()
    zip_file_name = input("Enter the name of the zip file (without .zip extension): ").strip()

    # Get the path to the ZIP file
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tools_dir)
    zip_dir = os.path.join(project_root, 'lambda_fns/zipped_fns')
    zip_path = os.path.join(zip_dir, f"{zip_file_name}.zip")

    if not os.path.exists(zip_path):
        print(f"Zipped function '{zip_file_name}.zip' not found in {zip_dir}")
        return

    # Read the ZIP file
    with open(zip_path, 'rb') as zip_file:
        zip_content = zip_file.read()

    try:
        # Try to get the function configuration
        lambda_client.get_function(FunctionName=function_name)
        
        # If the function exists, update it
        print(f"Updating existing Lambda function '{function_name}'...")
        response = lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_content
        )
        print("Lambda function code updated successfully.")
        
        # Update function configuration
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Runtime=runtime,
            Role=role_arn,
            Handler=handler
        )
        print("Lambda function configuration updated successfully.")

    except lambda_client.exceptions.ResourceNotFoundException:
        # If the function doesn't exist, create it
        print(f"Creating new Lambda function '{function_name}'...")
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime=runtime,
            Role=role_arn,
            Handler=handler,
            Code={'ZipFile': zip_content}
        )
        print("Lambda function created successfully.")

    # Print the function details
    print("\nLambda Function Details:")
    print(json.dumps(response, indent=2, default=str))

if __name__ == "__main__":
    create_or_update_lambda()