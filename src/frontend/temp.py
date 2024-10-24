import boto3
import os
from dotenv import load_dotenv

def check_claude_quotas():
    """
    Check AWS service quotas for Anthropic Claude models using credentials from .env file.
    Returns the quotas for InvokeModel requests per minute.
    """
    # Load environment variables from .env file
    load_dotenv()
    
    # Check if credentials are present
    print("Checking AWS credentials from .env file...")
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')

    if not aws_access_key or not aws_secret_key:
        print("AWS credentials not found in .env file!")
        print("Please create a .env file with the following variables:")
        print("AWS_ACCESS_KEY_ID=your_access_key")
        print("AWS_SECRET_ACCESS_KEY=your_secret_key")
        print("AWS_REGION=your_region (optional, defaults to us-east-1)")
        print(f"\nCurrent environment variables found:")
        print(f"AWS_ACCESS_KEY_ID: {'Present' if aws_access_key else 'Missing'}")
        print(f"AWS_SECRET_ACCESS_KEY: {'Present' if aws_secret_key else 'Missing'}")
        print(f"AWS_REGION: {aws_region}")
        return

    # Create boto3 client with explicit credentials
    client = boto3.client(
        'service-quotas',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )
    
    # Define the quotas we want to check
    quotas_to_check = [
        {
            'ServiceCode': 'bedrock',
            'QuotaCode': 'L-254CACF4', # On-demand InvokeModel requests per minute for Anthropic Claude 3.5 Sonnet
            'ModelName': 'Claude 3.5 Sonnet'
        },
        {
            'ServiceCode': 'bedrock',
            'QuotaCode': 'L-F406804E', # On-demand InvokeModel requests per minute for Anthropic Claude 3 Sonnet
            'ModelName': 'Claude 3 Sonnet'
        }
    ]
    
    print("\nChecking AWS Service Quotas for Claude models...")
    print("-" * 50)
    
    for quota in quotas_to_check:
        try:
            response = client.get_service_quota(
                ServiceCode=quota['ServiceCode'],
                QuotaCode=quota['QuotaCode']
            )
            print(response)
            
            quota_value = response['Quota']['Value']
            print(f"{quota['ModelName']}:")
            print(f"InvokeModel requests per minute: {quota_value}")
            print("-" * 50)
            
        except client.exceptions.NoSuchResourceException:
            print(f"Quota not found for {quota['ModelName']}")
        except Exception as e:
            print(f"Error checking quota for {quota['ModelName']}: {str(e)}")

if __name__ == "__main__":
    check_claude_quotas()