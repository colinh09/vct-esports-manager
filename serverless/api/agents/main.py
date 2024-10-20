import sys
import uuid
from vct_agent import process_vct_query_sync

def main():
    print("Welcome to the interactive VCT Query System. Type 'quit' to exit.")
    
    user_id = "user123"
    session_id = str(uuid.uuid4())  # Generate a session ID for the entire conversation
    
    print(f"Session ID: {session_id}")
    
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'quit':
            print("Exiting the program. Goodbye!")
            sys.exit()
        
        result = process_vct_query_sync(user_input, user_id, session_id)
        
        print("\nMetadata:")
        print(f"Selected Agent: {result['agent_name']}")
        print(f"Is Streaming: {result['is_streaming']}")
        print(f"Response: {result['content']}")

if __name__ == "__main__":
    main()