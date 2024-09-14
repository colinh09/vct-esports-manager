import json
from .base_agent import BaseAgent

class SqlAgent(BaseAgent):
    def __init__(self, region_name='us-east-1'):
        super().__init__("sql-vct-agent", region_name)
        self.agent_description = "Agent for providing Valorant esports statistics and player information"
        self.agent_instruction = """You are an esports manager assistant, helping users get information about Valorant players and tournaments. 
        When asked about a player, always use the get_player_info_by_handle function to retrieve information. 
        For player statistics, use get_player_game_stats or get_player_tournament_stats as appropriate. 
        Always use these functions to provide accurate, up-to-date information."""
        self.agent_foundation_model = "anthropic.claude-v2"
        self.lambda_function_name = "SQL"
        self.agent_functions = [
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

    def get_or_create_agent(self):
        try:
            response = self.bedrock_agent_client.list_agents()
            existing_agent = next((agent for agent in response['agentSummaries'] if agent['agentName'] == self.agent_name), None)
            if existing_agent:
                agent_id = existing_agent['agentId']
                self.logger.info(f"Using existing agent with ID: {agent_id}")
                
                # Fetch the agent alias
                alias_response = self.bedrock_agent_client.list_agent_aliases(agentId=agent_id)
                if alias_response['agentAliasSummaries']:
                    agent_alias_id = alias_response['agentAliasSummaries'][0]['agentAliasId']
                    self.logger.info(f"Using agent alias ID: {agent_alias_id}")
                    return agent_id, agent_alias_id
                else:
                    self.logger.error("No agent alias found. Please create an alias for the agent.")
                    return None, None
        except Exception as e:
            self.logger.error(f"Error checking for existing agent: {str(e)}")

        # If we reach here, we need to create a new agent
        role_name = f'AmazonBedrockExecutionRoleForAgents_{self.agent_name}'
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        
        try:
            role = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy)
            )
            self.logger.info(f"Created IAM role: {role_name}")
        except self.iam_client.exceptions.EntityAlreadyExistsException:
            role = self.iam_client.get_role(RoleName=role_name)
            self.logger.info(f"IAM role already exists: {role_name}")

        self.iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/AmazonBedrockFullAccess'
        )

        response = self.bedrock_agent_client.create_agent(
            agentName=self.agent_name,
            description=self.agent_description,
            instruction=self.agent_instruction,
            foundationModel=self.agent_foundation_model,
            idleSessionTTLInSeconds=300,
            agentResourceRoleArn=role['Role']['Arn']
        )
        
        agent_id = response['agent']['agentId']
        self.logger.info(f"Created new agent with ID: {agent_id}")
        
        # Create an alias for the new agent
        alias_response = self.bedrock_agent_client.create_agent_alias(
            agentId=agent_id,
            agentAliasName=f"{self.agent_name}-alias"
        )
        agent_alias_id = alias_response['agentAlias']['agentAliasId']
        self.logger.info(f"Created new agent alias with ID: {agent_alias_id}")
        
        return agent_id, agent_alias_id

    def create_agent_action_group(self, agent_id):
        try:
            response = self.bedrock_agent_client.create_agent_action_group(
                agentId=agent_id,
                agentVersion='DRAFT',
                actionGroupExecutor={
                    'lambda': f'arn:aws:lambda:{self.region_name}:{self.sts_client.get_caller_identity()["Account"]}:function:{self.lambda_function_name}'
                },
                actionGroupName='ValorantStatsActionGroup',
                description='Actions for querying Valorant player and team statistics',
                functionSchema={
                    'functions': self.agent_functions
                }
            )
            self.logger.info(f"Created agent action group: {response['agentActionGroup']['actionGroupId']}")
            
            # Add Lambda invoke permission
            try:
                self.lambda_client.add_permission(
                    FunctionName=self.lambda_function_name,
                    StatementId='allow_bedrock',
                    Action='lambda:InvokeFunction',
                    Principal='bedrock.amazonaws.com',
                    SourceArn=f"arn:aws:bedrock:{self.region_name}:{self.sts_client.get_caller_identity()['Account']}:agent/{agent_id}"
                )
                self.logger.info(f"Added Lambda invoke permission for Bedrock agent")
            except self.lambda_client.exceptions.ResourceConflictException:
                self.logger.info("Lambda invoke permission already exists")
            except Exception as e:
                self.logger.error(f"Error adding Lambda invoke permission: {str(e)}")
            
        except self.bedrock_agent_client.exceptions.ConflictException:
            self.logger.info("Action group already exists. Skipping creation.")

    def update_agent_action_group(self, agent_id):
        try:
            response = self.bedrock_agent_client.list_agent_action_groups(agentId=agent_id, agentVersion='DRAFT')
            action_group_id = response['agentActionGroupSummaries'][0]['actionGroupId']
            
            self.bedrock_agent_client.update_agent_action_group(
                agentId=agent_id,
                agentVersion='DRAFT',
                actionGroupId=action_group_id,
                actionGroupName='ValorantStatsActionGroup',
                description='Actions for querying Valorant player and team statistics',
                actionGroupExecutor={
                    'lambda': f'arn:aws:lambda:{self.region_name}:{self.sts_client.get_caller_identity()["Account"]}:function:{self.lambda_function_name}'
                },
                functionSchema={
                    'functions': self.agent_functions
                }
            )
            self.logger.info(f"Updated agent action group: {action_group_id}")
        except Exception as e:
            self.logger.error(f"Error updating action group: {str(e)}")