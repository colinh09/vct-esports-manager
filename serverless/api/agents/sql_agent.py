from multi_agent_orchestrator.agents import AmazonBedrockAgent, AmazonBedrockAgentOptions, AgentCallbacks
from botocore.config import Config
import boto3

class ValorantAgentCallbacks(AgentCallbacks):
    def on_llm_new_token(self, token: str) -> None:
        print(token, end='', flush=True)

def create_valorant_agent():
    # Define a custom configuration with increased timeouts
    custom_config = Config(
        connect_timeout=120,
        read_timeout=120, 
        retries={'max_attempts': 3}
    )

    custom_client = boto3.client('bedrock-agent-runtime', region_name='us-east-1', config=custom_config)

    valorant_agent = AmazonBedrockAgent(AmazonBedrockAgentOptions(
        name='sql-vct-agent',
        description='Agent for providing Valorant esports statistics and player information',
        agent_id='MOB0OFJEEO',
        agent_alias_id='S3EODLTXM8',
        region='us-east-1',
        client=custom_client 
    ))

    return valorant_agent