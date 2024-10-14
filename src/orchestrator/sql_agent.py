from multi_agent_orchestrator.agents import BedrockLLMAgent, BedrockLLMAgentOptions, AgentCallbacks

class ValorantAgentCallbacks(AgentCallbacks):
    def on_llm_new_token(self, token: str) -> None:
        print(token, end='', flush=True)

def create_valorant_agent():
    valorant_agent = BedrockLLMAgent(BedrockLLMAgentOptions(
        name='sql-vct-agent',
        description='Agent for providing Valorant esports statistics and player information',
        model_id='anthropic.claude-3-sonnet-20240229-v1:0',
        region='us-east-1',
        streaming=True,
        callbacks=ValorantAgentCallbacks()
    ))

    return valorant_agent