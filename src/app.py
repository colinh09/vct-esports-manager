import os
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
# from langchain_aws import ChatBedrock

from langchain_openai import ChatOpenAI
from tools.sql_tools import tools as sql_query_tools
from dotenv import load_dotenv

load_dotenv()
API_KEY =  os.getenv("OPEN_API_KEY")

# Commented out Titan code
# llm = ChatBedrock(
#     model_id="amazon.titan-text-express-v1",
#     model_kwargs=dict(temperature=0),
# )

llm = ChatOpenAI(
    model="gpt-3.5-turbo-0125",
    api_key=API_KEY, 
    temperature=0
)

# Custom prompt explicitly instructing the use of tools
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful assistant. You MUST use the provided tools to retrieve information. If a tool is available, always call it to answer questions."),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

# Create the tool-calling agent
agent = create_tool_calling_agent(
    llm=llm,
    tools=sql_query_tools,
    prompt=prompt
)

# Initialize AgentExecutor
agent_executor = AgentExecutor(agent=agent, tools=sql_query_tools)

def main():
    print("\nWelcome to the Valorant Esports Manager CLI")
    print("Type 'exit' to quit the application.\n")

    chat_history = []

    while True:
        user_input = input("Your prompt: ").strip()

        if user_input.lower() == 'exit':
            print("\nExiting the CLI. Goodbye!\n")
            break

        try:
            chat_history.append(HumanMessage(content=user_input))

            # Invoke the agent executor with input and chat history
            result = agent_executor.invoke({"input": user_input, "chat_history": chat_history})

            # Display the result and log tool usage for debugging
            if result:
                print("\nResults:\n" + "-" * 50)
                print(result)
                print("-" * 50 + "\n")
            else:
                print("\nNo results found.\n")

        except Exception as e:
            print(f"\nAn error occurred: {str(e)}\n")

if __name__ == "__main__":
    main()
