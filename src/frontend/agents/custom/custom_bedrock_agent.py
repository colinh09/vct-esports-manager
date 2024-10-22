from typing import List, Dict, Any, AsyncIterable, Optional, Union
from dataclasses import dataclass
from multi_agent_orchestrator.agents import BedrockLLMAgent, BedrockLLMAgentOptions
from multi_agent_orchestrator.types import ConversationMessage, ParticipantRole
from multi_agent_orchestrator.utils import conversation_to_dict
from datetime import datetime
import json

@dataclass 
class CustomBedrockLLMAgentOptions(BedrockLLMAgentOptions):
    pass

class CustomBedrockLLMAgent(BedrockLLMAgent):
    def __init__(self, options: CustomBedrockLLMAgentOptions):
        super().__init__(options)

    async def process_request(
        self,
        input_text: str,
        user_id: str,
        session_id: str,
        chat_history: List[ConversationMessage],
        additional_params: Optional[Dict[str, str]] = None
    ) -> Union[ConversationMessage, AsyncIterable[Any]]:
        
        user_message = ConversationMessage(
            role=ParticipantRole.USER.value,
            content=[{'text': input_text}]
        )

        conversation = [*chat_history, user_message]
        self.update_system_prompt()
        system_prompt = self.system_prompt

        if self.retriever:
            response = await self.retriever.retrieve_and_combine_results(input_text)
            context_prompt = "\nHere is the context to use to answer the user's question:\n" + response
            system_prompt += context_prompt

        converse_cmd = {
            'modelId': self.model_id,
            'messages': conversation_to_dict(conversation),
            'system': [{'text': system_prompt}],
            'inferenceConfig': self.inference_config
        }

        if self.guardrail_config:
            converse_cmd["guardrailConfig"] = self.guardrail_config

        if self.tool_config:
            converse_cmd["toolConfig"] = {'tools': self.tool_config["tool"]}
            continue_with_tools = True
            final_message: ConversationMessage = {'role': ParticipantRole.USER.value, 'content': []}
            max_recursions = self.tool_config.get('toolMaxRecursions', self.default_max_recursions)
            recursion_count = 0

            while continue_with_tools and max_recursions > 0:
                recursion_count += 1
                
                if self.streaming:
                    bedrock_response = await self.handle_streaming_response(converse_cmd)
                else:
                    bedrock_response = await self.handle_single_response(converse_cmd)

                conversation.append(bedrock_response)

                if any('toolUse' in content for content in bedrock_response.content):
                    tool_result = await self.tool_config['useToolHandler'](bedrock_response, conversation)
                    json_str= tool_result
                    tool_data = json.loads(json_str)
                    
                    tool_response = ConversationMessage(
                        role=ParticipantRole.USER.value,
                        content=[{
                            'toolResult': {
                                'toolUseId': bedrock_response.content[0]['toolUse']['toolUseId'],
                                'content': [{
                                    'json': tool_data
                                }]
                            }
                        }]
                    )
                    conversation.append(tool_response)
                else:
                    continue_with_tools = False
                    final_message = bedrock_response

                max_recursions -= 1
                converse_cmd['messages'] = conversation_to_dict(conversation)

            return final_message

        if self.streaming:
            return await self.handle_streaming_response(converse_cmd)

        return await self.handle_single_response(converse_cmd)