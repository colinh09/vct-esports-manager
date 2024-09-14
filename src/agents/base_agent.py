import boto3
import logging
import uuid
from botocore.exceptions import ClientError

class BaseAgent:
    def __init__(self, agent_name, region_name='us-east-1'):
        self.agent_name = agent_name
        self.region_name = region_name
        self.bedrock_agent_client = boto3.client('bedrock-agent', region_name=region_name)
        self.bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime', region_name=region_name)
        self.iam_client = boto3.client('iam', region_name=region_name)
        self.lambda_client = boto3.client('lambda', region_name=region_name)
        self.sts_client = boto3.client('sts', region_name=region_name)
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_or_create_agent(self):
        raise NotImplementedError("Subclasses must implement get_or_create_agent method")

    def create_agent_action_group(self, agent_id):
        raise NotImplementedError("Subclasses must implement create_agent_action_group method")

    def update_agent_action_group(self, agent_id):
        raise NotImplementedError("Subclasses must implement update_agent_action_group method")

    def prepare_agent(self, agent_id):
        try:
            response = self.bedrock_agent_client.prepare_agent(agentId=agent_id)
            self.logger.info(f"Prepared agent: {agent_id}")
            return response['agentStatus']
        except ClientError as e:
            self.logger.error(f"Error preparing agent: {str(e)}")
            raise

    def invoke_agent(self, agent_id, agent_alias_id, user_input):
        try:
            response = self.bedrock_agent_runtime_client.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=str(uuid.uuid4()),
                inputText=user_input,
                enableTrace=True
            )
            return response
        except ClientError as e:
            self.logger.error(f"Error invoking agent: {str(e)}")
            raise