from typing import Dict, Any, AsyncIterable, Optional, Union
from multi_agent_orchestrator.orchestrator import MultiAgentOrchestrator
from multi_agent_orchestrator.agents import (Agent,
                        AgentResponse,
                        AgentProcessingResult,
                        BedrockLLMAgent,
                        BedrockLLMAgentOptions)
from multi_agent_orchestrator.types import ConversationMessage, ParticipantRole, OrchestratorConfig
from multi_agent_orchestrator.utils import conversation_to_dict, Logger
from multi_agent_orchestrator.classifiers import ClassifierResult

class CustomMultiAgentOrchestrator(MultiAgentOrchestrator):
    async def dispatch_to_agent(self,
                              params: Dict[str, Any]) -> Union[
                                  ConversationMessage, AsyncIterable[Any]
                              ]:
        """
        Enhanced version of dispatch_to_agent that maintains full conversation history
        """
        user_input = params['user_input']
        user_id = params['user_id']
        session_id = params['session_id']
        classifier_result: ClassifierResult = params['classifier_result']
        additional_params = params.get('additional_params', {})

        self.logger.info(f"Dispatching request - User: {user_id}, Session: {session_id}")
        self.logger.info(f"Input text: {user_input}")

        if not classifier_result.selected_agent:
            self.logger.warn("No agent selected in classifier result")
            return "I'm sorry, but I need more information to understand your request. Could you please be more specific?"

        selected_agent = classifier_result.selected_agent
        self.logger.info(f"Selected agent: {selected_agent.name} ({selected_agent.id})")

        try:
            # Get the full conversation history
            chat_history = await self.storage.fetch_all_chats(user_id, session_id) or []
            self.logger.info(f"Fetched full chat history: {len(chat_history)} messages")
            
            if hasattr(self.logger, 'print_chat_history'):
                self.logger.print_chat_history(chat_history, "Full History")

            self.logger.info("Processing request with selected agent...")
            response = await self.measure_execution_time(
                f"Agent {selected_agent.name} | Processing request",
                lambda: selected_agent.process_request(user_input,
                                                     user_id,
                                                     session_id,
                                                     chat_history,  # Passing full chat history
                                                     additional_params)
            )

            # Log response details for debugging
            self.logger.info(f"Agent response type: {type(response)}")
            if response is None:
                self.logger.warn("Agent returned None response")
            elif isinstance(response, ConversationMessage):
                self.logger.info(f"ConversationMessage response with role: {response.role}")
                if hasattr(response, 'content'):
                    self.logger.info(f"Response content type: {type(response.content)}")
                    self.logger.info(f"Response content: {response.content[:100]}...")  # First 100 chars
            elif isinstance(response, dict):
                self.logger.info(f"Dict response with keys: {response.keys()}")
                if 'content' in response:
                    self.logger.info(f"Response content: {str(response['content'])[:100]}...")
            elif isinstance(response, str):
                self.logger.info(f"String response: {response[:100]}...")  # First 100 chars
            else:
                self.logger.info(f"Other response type: {type(response)}")

            return response

        except Exception as e:
            self.logger.error(f"Error in dispatch_to_agent: {str(e)}")
            raise

    # Keep your enhanced save_message method from before
    async def save_message(self,
                          message: Union[ConversationMessage, Dict[str, Any]],
                          user_id: str,
                          session_id: str,
                          agent: Agent):
        """
        Enhanced version of save_message that handles both ConversationMessage objects
        and dictionary-style messages with 'role' and 'content' fields.
        """
        self.logger.info(f"Attempting to save message for agent {agent.id if agent else 'None'}")
        self.logger.info(f"Message type: {type(message)}")
        
        if agent and agent.save_chat:
            # If it's already a ConversationMessage, use it directly
            if isinstance(message, ConversationMessage):
                conversation_message = message
                self.logger.info("Processing ConversationMessage")
            # If it's a dict with role and content, convert to ConversationMessage
            elif isinstance(message, dict) and 'role' in message and 'content' in message:
                self.logger.info("Converting dict to ConversationMessage")
                # Handle both string content and list of content blocks
                content = ([{'text': message['content']}] 
                          if isinstance(message['content'], str) 
                          else message['content'])
                conversation_message = ConversationMessage(
                    role=message['role'],
                    content=content
                )
            else:
                error_msg = "Message must be either a ConversationMessage or a dictionary with 'role' and 'content' fields"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            self.logger.info(f"Saving message to storage with role: {conversation_message.role}")
            return await self.storage.save_chat_message(
                user_id,
                session_id,
                agent.id,
                conversation_message,
                self.config.MAX_MESSAGE_PAIRS_PER_AGENT
            )