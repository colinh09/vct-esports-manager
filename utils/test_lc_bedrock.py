from langchain_aws import ChatBedrock
from langchain.schema import HumanMessage

# Initialize Bedrock with the correct model ID
llm = ChatBedrock(
    model_id="amazon.titan-text-express-v1",  # Or whatever model you're using
    model_kwargs=dict(temperature=0),
)

# Proper message structure (must pass a list)
response = llm.invoke([HumanMessage(content="What are the best strategies for playing Valorant?")])

# Print the response
print(response.content)
