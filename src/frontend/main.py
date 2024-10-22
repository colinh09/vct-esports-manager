import asyncio
import sys
from agents.vct_agent import VCTAgentSystem

async def initialize_and_test():
    vct_system = VCTAgentSystem()
    
    print("Testing AWS Bedrock...")
    try:
        bedrock_working = await vct_system.test_bedrock_classifier()
        if bedrock_working:
            print("AWS Bedrock is working. Using Bedrock classifier.")
        else:
            print("AWS Bedrock is throttled. Switching to Anthropic classifier...")
            await vct_system.switch_to_anthropic_classifier()
    except Exception as e:
        print(f"Unexpected error during initialization: {e}")
        sys.exit(1)
    
    return vct_system

async def async_main():
    # vct_system = await initialize_and_test()
    vct_system = VCTAgentSystem()
    await vct_system.switch_to_anthropic_classifier()
    
    print("VCT Agent System is ready.")
    print("Welcome to the interactive VCT Query System. Type 'quit' to exit.")
    
    user_id = "user123"
    session_id = "test_session"
    
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'quit':
            print("Exiting the program. Goodbye!")
            return
        
        try:
            result = await vct_system.process_query(user_input, user_id, session_id)
            print("\nMetadata:")
            print(f"Selected Agent: {result['agent_name']}")
            print(f"Is Streaming: {result['is_streaming']}")
            print(f"Response: {result['content']}")
        except Exception as e:
            print(f"Error processing query: {e}")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()