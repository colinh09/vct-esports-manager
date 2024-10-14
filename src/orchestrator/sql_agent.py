from multi_agent_orchestrator.agents import  AmazonBedrockAgent, AmazonBedrockAgentOptions, AgentCallbacks

class ValorantAgentCallbacks(AgentCallbacks):
    def on_llm_new_token(self, token: str) -> None:
        print(token, end='', flush=True)

def create_valorant_agent():

    valorant_agent = AmazonBedrockAgent(AmazonBedrockAgentOptions(
        name='sql-vct-agent',
        description='Agent for providing Valorant esports statistics and player information',
        agent_id='MOB0OFJEEO',
        agent_alias_id='S3EODLTXM8',
        region='us-east-1'
    ))

    return valorant_agent