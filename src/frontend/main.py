import asyncio
import sys
from agents.vct_agent import VCTAgentSystem

async def async_main():
    # Initialize the VCT system
    vct_system = VCTAgentSystem()
    
    print("Initializing VCT Agent System...")
    try:
        # This will automatically check quotas and select the appropriate service
        await vct_system.initialize()
    except Exception as e:
        print(f"Error during initialization: {e}")
        sys.exit(1)

    print("\nVCT Agent System is ready.")
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