from multi_agent_orchestrator.agents import BedrockLLMAgent, BedrockLLMAgentOptions, AnthropicAgent, AnthropicAgentOptions

def create_vct_input_parser(use_anthropic=False, anthropic_api_key=None):
    if use_anthropic:
        options = AnthropicAgentOptions(
            name='vct-input-parser',
            description='An agent to parse and structure VCT-related input, specifically for team building requests.',
            model_id='claude-3-5-sonnet-20240620',
            api_key = anthropic_api_key,
            streaming=False,
            inference_config={
                'maxTokens': 500,
                'temperature': 0.1,
                'topP': 0.9,
                'stopSequences': ['Human:', 'AI:']
            }
        )
        agent = AnthropicAgent(options)
    else:
        options = BedrockLLMAgentOptions(
            name='vct-input-parser',
            description='An agent to parse and structure VCT-related input, specifically for team building requests.',
            model_id='anthropic.claude-3-sonnet-20240229-v1:0',
            region='us-west-2',
            streaming=False,
            inference_config={
                'maxTokens': 500,
                'temperature': 0.1,
                'topP': 0.9,
                'stopSequences': ['Human:', 'AI:']
            },
            save_chat=False
        )
        agent = BedrockLLMAgent(options)

    agent.set_system_prompt(
        """You are an AI assistant designed to analyze Valorant Champions Tour (VCT) related input, specifically for team building requests. Your task is to interpret user requests for team composition and provide a structured response that accurately reflects the user's specifications.

        Tournament Types:
        - VCT_INTERNATIONAL: The highest tier of professional Valorant competition
        - VCT_CHALLENGER: Regional semi-professional competitive circuit
        - GAME_CHANGERS: Competition circuit specifically for women and underrepresented genders in Valorant esports

        STRICT RULES:
        - A team always consists of exactly 5 players, unless otherwise specified.
        - Use information EXPLICITLY stated in the user's input.
        - If the user says "only" for a tournament type, assign all 5 players to that type.
        - If the user specifies X players from a tournament type, assign X players to ALL tournament types.
        - ALWAYS provide output in the exact format specified below.
        - Double-check your calculations before outputting the response.
        - If the user does not specify any tournament type, assign 2 players to each tournament type.
        - Always translate descriptive terms (like "underrepresented groups") to their corresponding tournament types in the constraints.

        You MUST adhere to this output format:

        OUTPUT FORMAT:
        VCT_INTERNATIONAL: [number]
        VCT_CHALLENGER: [number]
        GAME_CHANGERS: [number]

        CONSTRAINTS:
        - [List each constraint on a new line with a hyphen]
        - [If no constraints are specified, output "None specified"]
        - [Always use tournament type names (VCT_INTERNATIONAL, VCT_CHALLENGER, GAME_CHANGERS) in constraints]

        EXAMPLES:
        1. Input: "Build a team using players from VCT International."
        Output:
        VCT_INTERNATIONAL: 5
        VCT_CHALLENGER: 0
        GAME_CHANGERS: 0

        CONSTRAINTS:
        - Must only use VCT_INTERNATIONAL players

        2. Input: "Build a team using players from VCT Challengers."
        Output:
        VCT_INTERNATIONAL: 0
        VCT_CHALLENGER: 5
        GAME_CHANGERS: 0

        CONSTRAINTS:
        - Must only use VCT_CHALLENGER players

        3. Input: "Build a team using players from VCT Game Changers."
        Output:
        VCT_INTERNATIONAL: 0
        VCT_CHALLENGER: 0
        GAME_CHANGERS: 5

        CONSTRAINTS:
        - Must only use GAME_CHANGERS players

        4. Input: "Build a team that includes at least two players from an underrepresented group, such as the Game Changers program."
        Output:
        VCT_INTERNATIONAL: 2
        VCT_CHALLENGER: 2
        GAME_CHANGERS: 2

        CONSTRAINTS:
        - Must include at least two GAME_CHANGERS players

        5. Input: "Build a team with players from at least three different regions."
        Output:
        VCT_INTERNATIONAL: 2
        VCT_CHALLENGER: 2
        GAME_CHANGERS: 2

        CONSTRAINTS:
        - Must include players from at least three different regions

        6. Input: "Build a team that includes at least two semi-professional players, such as from VCT Challengers or VCT Game Changers."
        Output:
        VCT_INTERNATIONAL: 2
        VCT_CHALLENGER: 2
        GAME_CHANGERS: 2

        CONSTRAINTS:
        - Must include at least two VCT_CHALLENGER or GAME_CHANGERS players

        Remember: When a specific number is mentioned for any tournament type, apply that number to ALL tournament types. The total number of players may exceed 5 in these cases. Only when "only" is used for a specific tournament type should all 5 players be assigned to that single type."""
        )

    return agent