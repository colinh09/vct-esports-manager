import uuid
import asyncio
import os
import boto3
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from multi_agent_orchestrator.orchestrator import MultiAgentOrchestrator, OrchestratorConfig
from multi_agent_orchestrator.agents import AgentResponse, ChainAgent, ChainAgentOptions
from multi_agent_orchestrator.classifiers import BedrockClassifier, BedrockClassifierOptions, AnthropicClassifier, AnthropicClassifierOptions
from multi_agent_orchestrator.storage import InMemoryChatStorage
from .input_parser_agent import create_vct_input_parser
from .general_agent import setup_player_analyst_agent
from .team_builder_agent import setup_team_builder_agent
from .final_agent import create_vct_final_agent
from .custom.custom_orchestrator import CustomMultiAgentOrchestrator

load_dotenv()

class VCTAgentSystem:
    def __init__(self, aws_access_key: str, aws_secret_key: str, anthropic_api_key: str, aws_region: str = 'us-east-1'):
        self.api_key = anthropic_api_key
        self.use_anthropic = False
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.aws_region = aws_region
        self.orchestrator = None

    def _check_bedrock_quotas(self) -> bool:
        """
        Check AWS service quotas for Claude models.
        Returns True if quotas are available (> 0), False otherwise.
        """
        if not self.aws_access_key or not self.aws_secret_key:
            print("AWS credentials not found in environment variables!")
            return False

        try:
            client = boto3.client(
                'service-quotas',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region
            )

            quotas_to_check = [
                {
                    'ServiceCode': 'bedrock',
                    'QuotaCode': 'L-254CACF4',
                    'ModelName': 'Claude 3.5 Sonnet'
                },
                {
                    'ServiceCode': 'bedrock',
                    'QuotaCode': 'L-F406804E',
                    'ModelName': 'Claude 3 Sonnet'
                }
            ]

            print("\nChecking AWS Service Quotas for Claude models...")
            print("-" * 50)
            
            total_quota = 0
            for quota in quotas_to_check:
                try:
                    response = client.get_service_quota(
                        ServiceCode=quota['ServiceCode'],
                        QuotaCode=quota['QuotaCode']
                    )
                    
                    quota_value = response['Quota']['Value']
                    print("Raw responses from AWS:")
                    print(response)
                    print(f"{quota['ModelName']}:")
                    print(f"InvokeModel requests per minute: {quota_value}")
                    print("-" * 50)
                    total_quota += float(quota_value)
                    
                except client.exceptions.NoSuchResourceException:
                    print(f"Quota not found for {quota['ModelName']}")
                except Exception as e:
                    print(f"Error checking quota for {quota['ModelName']}: {str(e)}")

            return total_quota > 0

        except Exception as e:
            print(f"Error connecting to AWS Service Quotas: {str(e)}")
            return False

    def _create_orchestrator(self, classifier=None):
        if classifier is None:
            classifier = BedrockClassifier(BedrockClassifierOptions(
                model_id='anthropic.claude-3-sonnet-20240229-v1:0',
                region=self.aws_region,
                inference_config={
                    'maxTokens': 500,
                    'temperature': 0.7,
                    'topP': 0.9,
                }
            ))
        memory_storage = InMemoryChatStorage()

        orchestrator = CustomMultiAgentOrchestrator(
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
            classifier=classifier,
            storage=memory_storage
        )


        chain_agent = self._create_chain_agent()
        analyst_agent = setup_player_analyst_agent(self.use_anthropic, self.api_key)
        orchestrator.add_agent(chain_agent)
        orchestrator.add_agent(analyst_agent)
        
        return orchestrator

    def _create_chain_agent(self):
        vct_input_parser = create_vct_input_parser(self.use_anthropic, self.api_key)
        team_builder_agent = setup_team_builder_agent(self.use_anthropic, self.api_key)
        
        chain_options = ChainAgentOptions(
            name='VCTChainAgent',
            description='This agent is responsible for building VCT teams. If the user mentions constructing a team, use this agent.',
            agents=[vct_input_parser, team_builder_agent],
            default_output='The chain processing encountered an issue.',
            save_chat=True
        )
        return ChainAgent(chain_options)

    async def switch_to_anthropic_classifier(self):
        self.use_anthropic = True
        print("\nSwitching to Anthropic API...")
        anthropic_classifier = AnthropicClassifier(AnthropicClassifierOptions(
            api_key=self.api_key,
            model_id='claude-3-sonnet-20240229'
        ))
        
        self.orchestrator = self._create_orchestrator(classifier=anthropic_classifier)
        print("Successfully configured Anthropic classifier")

    async def initialize(self):
        if self._check_bedrock_quotas():
            print("\nUsing AWS Bedrock for Claude models")
            self.orchestrator = self._create_orchestrator()
        else:
            print("\nNo AWS Bedrock quotas available or quota check failed")
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