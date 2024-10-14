import uuid
import asyncio
from typing import Optional, List, Dict, Any
import json
import sys
from multi_agent_orchestrator.orchestrator import MultiAgentOrchestrator, OrchestratorConfig
from multi_agent_orchestrator.agents import (
    BedrockLLMAgent,
    BedrockLLMAgentOptions,
    AgentResponse,
    AgentCallbacks,
    ChainAgent,
    ChainAgentOptions
)
from multi_agent_orchestrator.types import ConversationMessage, ParticipantRole
from multi_agent_orchestrator.classifiers import BedrockClassifier, BedrockClassifierOptions

# Create a custom Bedrock classifier
custom_bedrock_classifier = BedrockClassifier(BedrockClassifierOptions(
    model_id='anthropic.claude-3-haiku-20240307-v1:0',
    region='us-east-1',
    inference_config={
        'maxTokens': 500,
        'temperature': 0.7,
        'topP': 0.9
    }
))

# Create the orchestrator with the custom classifier
orchestrator = MultiAgentOrchestrator(
    options=OrchestratorConfig(
        LOG_AGENT_CHAT=True,
        LOG_CLASSIFIER_CHAT=True,
        LOG_CLASSIFIER_RAW_OUTPUT=True,
        LOG_CLASSIFIER_OUTPUT=True,
        LOG_EXECUTION_TIMES=True,
        MAX_RETRIES=3,
        USE_DEFAULT_AGENT_IF_NONE_IDENTIFIED=True,
        MAX_MESSAGE_PAIRS_PER_AGENT=10
    ),
    classifier=custom_bedrock_classifier
)

class ValorantAgentCallbacks(AgentCallbacks):
    def on_llm_new_token(self, token: str) -> None:
        # handle response streaming here
        print(token, end='', flush=True)

# Create the first agent (vct-input-parser)
vct_input_parser = BedrockLLMAgent(BedrockLLMAgentOptions(
    name='vct-input-parser',
    description='An agent to parse the user input to extract relevant information about the query. This will make it easier for subsequent agents to determine what tools to use.',
    model_id='anthropic.claude-3-sonnet-20240229-v1:0',
    region='us-east-1'
))

# Create the second agent (sql-vct-agent)
valorant_agent = BedrockLLMAgent(BedrockLLMAgentOptions(
    name='sql-vct-agent',
    description='Agent for providing Valorant esports statistics and player information',
    model_id='anthropic.claude-3-sonnet-20240229-v1:0',
    region='us-east-1',
    streaming=True,
    callbacks=ValorantAgentCallbacks()
))

# Create the ChainAgent
chain_options = ChainAgentOptions(
    name='VCTChainAgent',
    description='A chain of agents for processing Valorant esports queries',
    agents=[vct_input_parser, valorant_agent],
    default_output='The chain processing encountered an issue.',
    save_chat=True
)
chain_agent = ChainAgent(chain_options)

# Add the chain agent to the orchestrator
orchestrator.add_agent(chain_agent)

async def handle_request(_orchestrator: MultiAgentOrchestrator, _user_input: str, _user_id: str, _session_id: str):
    response: AgentResponse = await _orchestrator.route_request(_user_input, _user_id, _session_id)
    
    # Print metadata
    print("\nMetadata:")
    print(f"Selected Agent: {response.metadata.agent_name}")
    
    if response.streaming:
        print('Response:', response.output.content[0]['text'])
    else:
        print('Response:', response.output.content[0]['text'])

if __name__ == "__main__":
    USER_ID = "user123"
    SESSION_ID = str(uuid.uuid4())
    print("Welcome to the interactive Multi-Agent system. Type 'quit' to exit.")
    
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'quit':
            print("Exiting the program. Goodbye!")
            sys.exit()
        
        # Run the async function
        asyncio.run(handle_request(orchestrator, user_input, USER_ID, SESSION_ID))