import os
from chains.sql_chain import run_sql_chain

def main():
    """
    CLI Application to query the SQL chain and display results.
    Users can input any question, and the SQL chain will generate and execute
    the corresponding SQL query, displaying the results in the terminal.
    """
    print("\nWelcome to the Valorant Esports Manager CLI")
    print("Type your question and I'll query the database for you!")
    print("For example, ask: 'Who are the top players in the last tournament?'")
    print("Type 'exit' to quit the application.\n")
    
    while True:
        user_input = input("Your prompt: ").strip()
        
        if user_input.lower() == 'exit':
            print("\nExiting the CLI. Goodbye!\n")
            break
        
        try:
            results = run_sql_chain(user_input)
            
            if results:
                print("\nResults:\n" + "-" * 50)
                for row in results:
                    print(" | ".join(map(str, row))) 
                print("-" * 50 + "\n")
            else:
                print("\nNo results found.\n")
        
        except Exception as e:
            print(f"\nAn error occurred: {str(e)}\n")

if __name__ == "__main__":
    main()
