import logging
from agents.sql_agent import SqlAgent
from utils.aws_utils import check_aws_permissions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    check_aws_permissions()
    
    sql_agent = SqlAgent()
    agent_id, agent_alias_id = sql_agent.get_or_create_agent()
    if not agent_id or not agent_alias_id:
        logger.error("Failed to get or create agent. Exiting.")
        return

    sql_agent.create_agent_action_group(agent_id)
    sql_agent.update_agent_action_group(agent_id)
    sql_agent.prepare_agent(agent_id)

    print("\nWelcome to the Valorant Esports Manager CLI")
    print("Type 'exit' to quit the application.\n")
    
    while True:
        user_input = input("Your prompt: ").strip()
        
        if user_input.lower() == 'exit':
            print("\nExiting the CLI. Goodbye!\n")
            break
        
        try:
            response = sql_agent.invoke_agent(agent_id, agent_alias_id, user_input)
            print("\nAgent response:\n" + "-" * 50)
            for event in response['completion']:
                if 'chunk' in event:
                    print(event['chunk']['bytes'].decode('utf-8'), end='', flush=True)
                elif 'trace' in event:
                    logger.info(f"Trace: {json.dumps(event['trace'], indent=2)}")
            print("\n" + "-" * 50 + "\n")
        
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            print(f"\nAn error occurred: {str(e)}\n")

if __name__ == "__main__":
    main()