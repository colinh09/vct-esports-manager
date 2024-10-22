from multi_agent_orchestrator.agents import BedrockLLMAgent, BedrockLLMAgentOptions

def create_test_agent():
    test_agent = BedrockLLMAgent(BedrockLLMAgentOptions(
        name='vct-input-parser',
        description='An agent that will fetch data from database',
        model_id='ai21.jamba-1-5-mini-v1:0',
        region='us-east-1',
        streaming=False,
        inference_config={
            'maxTokens': 500,
            'temperature': 0.1,
            'topP': 0.9,
            'stopSequences': ['Human:', 'AI:']
        },
        save_chat = False,
    ))

    return test_agent