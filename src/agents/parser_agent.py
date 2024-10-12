import json
from .base_agent import BaseAgent

class VctInputParserAgent(BaseAgent):
    def __init__(self, region_name='us-east-1'):
        super().__init__("vct-input-parser", region_name)
        self.agent_id = "T3Q9I6LDW4"
        self.agent_arn = "arn:aws:bedrock:us-east-1:423623863958:agent/T3Q9I6LDW4"
        self.agent_instruction = """
        You are an AI assistant specialized in parsing and understanding input related to the Valorant Champions Tour (VCT).
        Your task is to analyze user input and extract relevant information, such as:
        - Player names (first and last name)
        - Player handles (in-game names)
        - Team names
        - League names
        - Regions
        - Tournament types (limited to: vct-challengers, vct-international, game-changers)

        Do not make any external function calls or API requests. Your role is to process and understand the input, not to retrieve additional information.

        When given input, provide a structured analysis of the relevant information you've identified. 
        If certain types of information are not present in the input, simply omit them from your analysis.

        Example input and output:
        Input: "Tell me about TenZ's performance in the last VCT International tournament."
        Output: {
            "player_handle": "TenZ",
            "tournament_type": "vct-international"
        }

        Always respond with a JSON object containing the extracted information. If no relevant information is found, return an empty JSON object.
        """

    def get_agent(self):
        try:
            response = self.bedrock_agent_client.get_agent(
                agentId=self.agent_id
            )
            self.logger.info(f"Retrieved existing agent: {self.agent_id}")
            
            # Fetch the agent alias
            alias_response = self.bedrock_agent_client.list_agent_aliases(agentId=self.agent_id)
            if alias_response['agentAliasSummaries']:
                agent_alias_id = alias_response['agentAliasSummaries'][0]['agentAliasId']
                self.logger.info(f"Using agent alias ID: {agent_alias_id}")
                return self.agent_id, agent_alias_id
            else:
                self.logger.error("No agent alias found. Please create an alias for the agent.")
                return self.agent_id, None
        except Exception as e:
            self.logger.error(f"Error retrieving existing agent: {str(e)}")
            return None, None

    def update_agent_instructions(self):
        try:
            response = self.bedrock_agent_client.update_agent(
                agentId=self.agent_id,
                instruction=self.agent_instruction
            )
            self.logger.info(f"Updated agent instructions for: {self.agent_id}")
            return response['agent']
        except Exception as e:
            self.logger.error(f"Error updating agent instructions: {str(e)}")
            return None

    def invoke_agent(self, user_input, agent_alias_id=None):
        if not agent_alias_id:
            _, agent_alias_id = self.get_agent()
        
        if not agent_alias_id:
            self.logger.error("No agent alias ID available. Cannot invoke agent.")
            return None

        # Ensure instructions are up to date before invoking
        self.update_agent_instructions()

        try:
            return super().invoke_agent(self.agent_id, agent_alias_id, user_input)
        except Exception as e:
            self.logger.error(f"Error invoking agent: {str(e)}")
            if "Access denied" in str(e):
                self.logger.error("This may be due to insufficient IAM permissions. Please check your IAM role.")
            elif "ResourceNotFoundException" in str(e):
                self.logger.error("The specified agent or alias might not exist. Please verify the agent configuration.")
            raise

# Usage example:
# vct_agent = VctInputParserAgent()
# agent_id, agent_alias_id = vct_agent.get_agent()
# response = vct_agent.invoke_agent("Tell me about TenZ's performance in the last VCT International tournament.", agent_alias_id)