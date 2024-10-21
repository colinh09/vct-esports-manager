import uuid
import asyncio
from typing import Optional, Dict, Any
from multi_agent_orchestrator.orchestrator import MultiAgentOrchestrator, OrchestratorConfig
from multi_agent_orchestrator.agents import AgentResponse, ChainAgent, ChainAgentOptions
from multi_agent_orchestrator.classifiers import BedrockClassifier, BedrockClassifierOptions

from input_parser_agent import create_vct_input_parser
from sql_agent import create_valorant_agent
from final_agent import create_vct_final_agent

class VCTAgentSystem:
    def __init__(self):
        self.orchestrator = self._create_orchestrator()

    def _create_orchestrator(self):
        custom_bedrock_classifier = BedrockClassifier(BedrockClassifierOptions(
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
            classifier=custom_bedrock_classifier
        )

        vct_input_parser = create_vct_input_parser()
        valorant_agent = create_valorant_agent()
        final_agent = create_vct_final_agent()

        chain_options = ChainAgentOptions(
            name='VCTChainAgent',
            description='A chain of agents for processing Valorant esports queries',
            agents=[vct_input_parser, valorant_agent, final_agent],
            default_output='The chain processing encountered an issue.',
            save_chat=True
        )
        chain_agent = ChainAgent(chain_options)

        orchestrator.add_agent(chain_agent)
        
        return orchestrator

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

async def process_vct_query(user_input: str, user_id: str = "user123", session_id: Optional[str] = None) -> Dict[str, Any]:
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    return await vct_system.process_query(user_input, user_id, session_id)

# This function can be used for synchronous calls
def process_vct_query_sync(user_input: str, user_id: str = "user123", session_id: Optional[str] = None) -> Dict[str, Any]:
    return asyncio.run(process_vct_query(user_input, user_id, session_id))