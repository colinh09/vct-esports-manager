import boto3
import json
import os
import uuid
from dotenv import load_dotenv
import logging

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Bedrock clients
bedrock_agent_client = boto3.client('bedrock-agent', region_name='us-east-1')
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
iam_client = boto3.client('iam', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')
sts_client = boto3.client('sts', region_name='us-east-1')

# Configuration variables
agent_name = "valorant-esports-manager"
agent_description = "Agent for providing Valorant esports statistics and player information"
agent_instruction = """You are an esports manager assistant, helping users get information about Valorant players and tournaments. 
When asked about a player, always use the get_player_info_by_handle function to retrieve information. 
For player statistics, use get_player_game_stats or get_player_tournament_stats as appropriate. 
Always use these functions to provide accurate, up-to-date information."""
agent_foundation_model = "anthropic.claude-v2"
lambda_function_name = "SQL"
region = "us-east-1"

# Get account ID
account_id = sts_client.get_caller_identity()["Account"]

# Define your agent functions
agent_functions = [
    {
        'name': 'get_player_info_by_handle',
        'description': 'Get information about a player based on their handle',
        'parameters': {
            "handle": {
                "description": "The handle (nickname) of the player",
                "required": True,
                "type": "string"
            }
        }
    },
    {
        'name': 'get_player_game_stats',
        'description': 'Get game statistics for a player',
        'parameters': {
            "player_id": {
                "description": "The ID of the player",
                "required": True,
                "type": "string"
            }
        }
    },
    {
        'name': 'get_player_tournament_stats',
        'description': 'Get tournament statistics for a player',
        'parameters': {
            "player_id": {
                "description": "The ID of the player",
                "required": True,
                "type": "string"
            },
            "tournament_id": {
                "description": "The ID of the tournament",
                "required": True,
                "type": "string"
            }
        }
    }
]

def check_aws_permissions():
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

def get_or_create_agent():
    try:
        response = bedrock_agent_client.list_agents()
        existing_agent = next((agent for agent in response['agentSummaries'] if agent['agentName'] == agent_name), None)
        if existing_agent:
            agent_id = existing_agent['agentId']
            logger.info(f"Using existing agent with ID: {agent_id}")
            
            # Fetch the agent alias
            alias_response = bedrock_agent_client.list_agent_aliases(agentId=agent_id)
            if alias_response['agentAliasSummaries']:
                agent_alias_id = alias_response['agentAliasSummaries'][0]['agentAliasId']
                logger.info(f"Using agent alias ID: {agent_alias_id}")
                return agent_id, agent_alias_id
            else:
                logger.error("No agent alias found. Please create an alias for the agent.")
                return None, None
    except Exception as e:
        logger.error(f"Error checking for existing agent: {str(e)}")

    # If we reach here, we need to create a new agent
    role_name = f'AmazonBedrockExecutionRoleForAgents_{agent_name}'
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }
    
    try:
        role = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy)
        )
        logger.info(f"Created IAM role: {role_name}")
    except iam_client.exceptions.EntityAlreadyExistsException:
        role = iam_client.get_role(RoleName=role_name)
        logger.info(f"IAM role already exists: {role_name}")

    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn='arn:aws:iam::aws:policy/AmazonBedrockFullAccess'
    )

    response = bedrock_agent_client.create_agent(
        agentName=agent_name,
        description=agent_description,
        instruction=agent_instruction,
        foundationModel=agent_foundation_model,
        idleSessionTTLInSeconds=300,
        agentResourceRoleArn=role['Role']['Arn']
    )
    
    agent_id = response['agent']['agentId']
    logger.info(f"Created new agent with ID: {agent_id}")
    
    # Create an alias for the new agent
    alias_response = bedrock_agent_client.create_agent_alias(
        agentId=agent_id,
        agentAliasName=f"{agent_name}-alias"
    )
    agent_alias_id = alias_response['agentAlias']['agentAliasId']
    logger.info(f"Created new agent alias with ID: {agent_alias_id}")
    
    return agent_id, agent_alias_id

def create_agent_action_group(agent_id):
    try:
        response = bedrock_agent_client.create_agent_action_group(
            agentId=agent_id,
            agentVersion='DRAFT',
            actionGroupExecutor={
                'lambda': f'arn:aws:lambda:{region}:{account_id}:function:{lambda_function_name}'
            },
            actionGroupName='ValorantStatsActionGroup',
            description='Actions for querying Valorant player and team statistics',
            functionSchema={
                'functions': agent_functions
            }
        )
        logger.info(f"Created agent action group: {response['agentActionGroup']['actionGroupId']}")
        
        # Add Lambda invoke permission
        try:
            lambda_client.add_permission(
                FunctionName=lambda_function_name,
                StatementId='allow_bedrock',
                Action='lambda:InvokeFunction',
                Principal='bedrock.amazonaws.com',
                SourceArn=f"arn:aws:bedrock:{region}:{account_id}:agent/{agent_id}"
            )
            logger.info(f"Added Lambda invoke permission for Bedrock agent")
        except lambda_client.exceptions.ResourceConflictException:
            logger.info("Lambda invoke permission already exists")
        except Exception as e:
            logger.error(f"Error adding Lambda invoke permission: {str(e)}")
        
    except bedrock_agent_client.exceptions.ConflictException:
        logger.info("Action group already exists. Skipping creation.")

def update_agent_action_group(agent_id):
    try:
        response = bedrock_agent_client.list_agent_action_groups(agentId=agent_id, agentVersion='DRAFT')
        action_group_id = response['agentActionGroupSummaries'][0]['actionGroupId']
        
        bedrock_agent_client.update_agent_action_group(
            agentId=agent_id,
            agentVersion='DRAFT',
            actionGroupId=action_group_id,
            actionGroupName='ValorantStatsActionGroup',
            description='Actions for querying Valorant player and team statistics',
            actionGroupExecutor={
                'lambda': f'arn:aws:lambda:{region}:{account_id}:function:{lambda_function_name}'
            },
            functionSchema={
                'functions': agent_functions
            }
        )
        logger.info(f"Updated agent action group: {action_group_id}")
    except Exception as e:
        logger.error(f"Error updating action group: {str(e)}")

def prepare_agent(agent_id):
    response = bedrock_agent_client.prepare_agent(agentId=agent_id)
    logger.info(f"Prepared agent: {agent_id}")
    return response['agentStatus']

def invoke_agent(agent_id, agent_alias_id, user_input):
    response = bedrock_agent_runtime_client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=str(uuid.uuid4()),
        inputText=user_input,
        enableTrace=True
    )
    
    for event in response['completion']:
        if 'chunk' in event:
            chunk = event['chunk']['bytes'].decode('utf-8')
            yield chunk
        elif 'trace' in event:
            trace = event['trace']
            logger.info(f"Trace: {json.dumps(trace, indent=2)}")
            if 'functionCalledResponseBody' in trace:
                function_response = json.loads(trace['functionCalledResponseBody'])
                if 'responseBody' in function_response:
                    text_body = function_response['responseBody'].get('TEXT', {}).get('body', '{}')
                    yield f"Function call result: {json.dumps(json.loads(text_body), indent=2)}"

def main():
    check_aws_permissions()
    
    agent_id, agent_alias_id = get_or_create_agent()
    if not agent_id or not agent_alias_id:
        logger.error("Failed to get or create agent. Exiting.")
        return

    create_agent_action_group(agent_id)
    update_agent_action_group(agent_id)
    prepare_agent(agent_id)

    print("\nWelcome to the Valorant Esports Manager CLI")
    print("Type 'exit' to quit the application.\n")
    
    while True:
        user_input = input("Your prompt: ").strip()
        
        if user_input.lower() == 'exit':
            print("\nExiting the CLI. Goodbye!\n")
            break
        
        try:
            print("\nAgent response:\n" + "-" * 50)
            for chunk in invoke_agent(agent_id, agent_alias_id, user_input):
                print(chunk, end='', flush=True)
            print("\n" + "-" * 50 + "\n")
        
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            print(f"\nAn error occurred: {str(e)}\n")

if __name__ == "__main__":
    main()