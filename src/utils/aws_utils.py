import boto3
import json
import logging

logger = logging.getLogger(__name__)

def check_aws_permissions(region_name='us-east-1'):
    sts_client = boto3.client('sts', region_name=region_name)
    bedrock_agent_client = boto3.client('bedrock-agent', region_name=region_name)

    logger.info("Checking AWS permissions...")
    try:
        identity = sts_client.get_caller_identity()
        logger.info(f"Current AWS identity: {json.dumps(identity, indent=2)}")
    except Exception as e:
        logger.error(f"Error getting AWS identity: {str(e)}")
    
    try:
        agents = bedrock_agent_client.list_agents()
        logger.info(f"Successfully listed Bedrock agents: {len(agents['agentSummaries'])} agents found")
    except Exception as e:
        logger.error(f"Error listing Bedrock agents: {str(e)}")