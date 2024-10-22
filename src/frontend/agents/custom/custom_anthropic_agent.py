from typing import List, Dict, Any, AsyncIterable, Optional, Union
from multi_agent_orchestrator.agents import AnthropicAgent, AnthropicAgentOptions
from multi_agent_orchestrator.types import ConversationMessage, ParticipantRole
from multi_agent_orchestrator.utils import Logger
import json

class CustomAnthropicAgent(AnthropicAgent):
    async def process_request(
        self,
        input_text: str,
        user_id: str,
        session_id: str,
        chat_history: List[ConversationMessage],
        additional_params: Optional[Dict[str, str]] = None
    ) -> Union[ConversationMessage, AsyncIterable[Any]]:
        try:
            if not self.tool_config:
                return await super().process_request(input_text, user_id, session_id, chat_history, additional_params)

            Logger.info(f"[Tool Call] Processing request with tools for session {session_id}")
            
            messages = [{"role": "user" if msg.role == ParticipantRole.USER.value else "assistant",
                        "content": msg.content[0]['text'] if msg.content else ''} for msg in chat_history]
            messages.append({"role": "user", "content": input_text})
            Logger.info(f"[Tool Call] Prepared messages: {json.dumps(messages[-1], indent=2)}")

            self.update_system_prompt()
            system_prompt = self.system_prompt

            input = {
                "model": self.model_id,
                "max_tokens": self.inference_config.get('maxTokens'),
                "messages": messages,
                "system": system_prompt,
                "temperature": self.inference_config.get('temperature'),
                "top_p": self.inference_config.get('topP'),
                "stop_sequences": self.inference_config.get('stopSequences'),
                "tools": self.tool_config["tool"]
            }

            final_message = ''
            tool_use = True
            recursions = self.tool_config.get('toolMaxRecursions') if self.tool_config else self.default_max_recursions
            Logger.info("Got here")
            while tool_use and recursions > 0:
                Logger.info(f"[Tool Call] Starting tool call iteration {self.default_max_recursions - recursions + 1}")
                
                if self.streaming:
                    response = await self.handle_streaming_response(input)
                else:
                    response = await self.handle_single_response(input)

                tool_use_blocks = [content for content in response.content if content.type == 'tool_use']
                
                if tool_use_blocks:
                    Logger.info(f"[Tool Call] Tool use detected in response: {json.dumps(tool_use_blocks[0].text, indent=2)}")
                    input['messages'].append({"role": "assistant", "content": response.content})
                    
                    if not self.tool_config or not self.tool_config.get('useToolHandler'):
                        raise ValueError("No tools available for tool use")
                    
                    Logger.info("[Tool Call] Calling tool handler")
                    tool_response = await self.tool_config['useToolHandler'](response, input['messages'])
                    Logger.info(f"[Tool Call] Tool handler response received: {json.dumps(tool_response, indent=2)}")
                    
                    input['messages'].append(tool_response)
                    tool_use = True
                else:
                    Logger.info("[Tool Call] No tool use detected in response")
                    text_content = next((content for content in response.content if content.type == 'text'), None)
                    final_message = text_content.text if text_content else ''
                    tool_use = False

                if response.stop_reason == 'end_turn':
                    Logger.info("[Tool Call] End turn detected")
                    tool_use = False

                recursions -= 1

            return ConversationMessage(role=ParticipantRole.ASSISTANT.value, content=[{'text': final_message}])

        except Exception as error:
            Logger.error(f"[Tool Call] Error in custom process_request: {str(error)}")
            raise error