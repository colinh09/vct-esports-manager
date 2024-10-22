from multi_agent_orchestrator.agents import BedrockLLMAgent, BedrockLLMAgentOptions

def create_vct_final_agent():
    vct_final_agent = BedrockLLMAgent(BedrockLLMAgentOptions(
        name='final-agent',
        description='An agent that will take a list of players and construct a final team.',
        model_id='ai21.jamba-1-5-mini-v1:0',
        region='us-east-1',
        streaming=False,
        inference_config={
            'maxTokens': 3000,
            'temperature': 0.1,
            'topP': 0.9,
            'stopSequences': ['Human:', 'AI:']
        },
        tool_config=None
    ))

    vct_final_agent.set_system_prompt(
        """Pretend you are a pro analyst and team builder for VCT (Valorant's esports league). Build a team by picking a duelist, and then build a team around that player.
        Produce a final team and explain why you chose each player. Also provide all of the player's stats and use it to reason why that player is a good fit for the team.
        Any time you mention a stat, include the number either within the sentence or in paranthesis (i.e. kills (36), assists (10))"""
    )

    return vct_final_agent