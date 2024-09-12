import os
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv
from tools.sql_tools import tools as sql_query_tools
from langchain.agents import AgentExecutor, create_tool_calling_agent

load_dotenv()
API_KEY = os.getenv("OPEN_API_KEY")

bedrock_agent = ChatBedrock(
    model_id="amazon.titan-text-express-v1",
    model_kwargs=dict(temperature=0),
)

openai_agent = ChatOpenAI(
    model="gpt-4",
    api_key=API_KEY,
    temperature=0
)

tool_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful assistant. You MUST use the provided tools to retrieve information. If a tool is available, always call it to answer questions."),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

bedrock_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are an assistant that takes structured information and formats it in a readable and insightful way."),
        ("human", "{input}")
    ]
)

agent = create_tool_calling_agent(
    llm=openai_agent,
    tools=sql_query_tools,
    prompt=tool_prompt
)

agent_executor = AgentExecutor(agent=agent, tools=sql_query_tools)

def extract_agent_output(agent_result):
    return agent_result['output']

chain = (
    {"input": RunnablePassthrough()}
    | agent_executor
    | extract_agent_output
    | bedrock_prompt
    | bedrock_agent
    | StrOutputParser()
)

def main():
    print("\nWelcome to the Valorant Esports Manager CLI")
    print("Type 'exit' to quit the application.\n")
    
    while True:
        user_input = input("Your prompt: ").strip()
        
        if user_input.lower() == 'exit':
            print("\nExiting the CLI. Goodbye!\n")
            break
        
        try:
            result = chain.invoke({"input": user_input})
            
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