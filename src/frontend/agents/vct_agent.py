import uuid
import asyncio
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from multi_agent_orchestrator.orchestrator import MultiAgentOrchestrator, OrchestratorConfig
from multi_agent_orchestrator.agents import AgentResponse, ChainAgent, ChainAgentOptions
from multi_agent_orchestrator.classifiers import BedrockClassifier, BedrockClassifierOptions, AnthropicClassifier, AnthropicClassifierOptions

from .input_parser_agent import create_vct_input_parser
from .general_agent import setup_player_info_agent
from .team_builder_agent import setup_team_builder_agent
from .final_agent import create_vct_final_agent

load_dotenv()

class VCTAgentSystem:
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        self.use_anthropic = False
        self.orchestrator = self._create_orchestrator()

    def _create_orchestrator(self, classifier=None):
        if classifier is None:
            classifier = BedrockClassifier(BedrockClassifierOptions(
                model_id='anthropic.claude-3-haiku-20240307-v1:0',
                region='us-east-1',
                inference_config={
                    'maxTokens': 500,
                    'temperature': 0.7,
                    'topP': 0.9,
                }
            ))

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
            classifier=classifier
        )

        chain_agent = self._create_chain_agent()
        orchestrator.add_agent(chain_agent)
        
        return orchestrator

    def _create_chain_agent(self):
        vct_input_parser = create_vct_input_parser(self.use_anthropic, self.api_key)
        team_builder_agent = setup_team_builder_agent(self.use_anthropic, self.api_key)

        chain_options = ChainAgentOptions(
            name='VCTChainAgent',
            description='A chain of agents for processing Valorant esports queries',
            agents=[vct_input_parser, team_builder_agent],
            default_output='The chain processing encountered an issue.',
            save_chat=True
        )
        return ChainAgent(chain_options)

    async def test_bedrock_classifier(self):
        test_input = "This is a test query."
        try:
            response = await self.orchestrator.route_request(test_input, "test_user", "test_session")
            
            if (response.metadata.additional_params and 
                response.metadata.additional_params.get('error_type') == 'classification_failed'):
                print("AWS Bedrock classification failed.")
                return False
            
            if "ThrottlingException" in response.output:
                print("AWS Bedrock is experiencing throttling issues.")
                return False
            
            print("Bedrock classifier test successful.")
            return True
            
        except Exception as e:
            print(f"Unexpected error during Bedrock classifier test: {str(e)}")
            return False

    async def switch_to_anthropic_classifier(self):
        self.use_anthropic = True
        anthropic_classifier = AnthropicClassifier(AnthropicClassifierOptions(
            api_key=self.api_key
        ))
        
        self.orchestrator = self._create_orchestrator(classifier=anthropic_classifier)

    async def initialize(self):
        if not await self.test_bedrock_classifier():
            await self.switch_to_anthropic_classifier()

    async def process_query(self, user_input: str, user_id: str, session_id: str) -> Dict[str, Any]:
        response: AgentResponse = await self.orchestrator.route_request(user_input, user_id, session_id)
        print(response)
        result = {
            "agent_name": response.metadata.agent_name,
            "content": response.output.content[0]['text'] if response.output.content else "",
            "is_streaming": response.streaming
        }
        
        return result

# Global instance of VCTAgentSystem
vct_system = VCTAgentSystem()

async def initialize_vct_system():
    await vct_system.initialize()

async def process_vct_query(user_input: str, user_id: str = "user123", session_id: Optional[str] = None) -> Dict[str, Any]:
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    return await vct_system.process_query(user_input, user_id, session_id)

# This function can be used for synchronous calls
def process_vct_query_sync(user_input: str, user_id: str = "user123", session_id: Optional[str] = None) -> Dict[str, Any]:
    return asyncio.run(process_vct_query(user_input, user_id, session_id))