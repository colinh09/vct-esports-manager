import streamlit as st
import logging
import json
from io import StringIO
import sys

# Adjust imports as needed
sys.path.append('..')
from agents.sql_agent import SqlAgent
from utils.aws_utils import check_aws_permissions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redirect logging to a string buffer
log_stream = StringIO()
logging_handler = logging.StreamHandler(log_stream)
logger.addHandler(logging_handler)

# Streamlit app
st.title("Valorant Esports Manager Chatbot")

# Initialize SqlAgent and get agent details
@st.cache_resource
def initialize_agent():
    check_aws_permissions()
    sql_agent = SqlAgent()
    agent_id, agent_alias_id = sql_agent.get_or_create_agent()
    if not agent_id or not agent_alias_id:
        st.error("Failed to get or create agent. Please check your AWS permissions and try again.")
        return None, None, None
    sql_agent.create_agent_action_group(agent_id)
    sql_agent.update_agent_action_group(agent_id)
    sql_agent.prepare_agent(agent_id)
    return sql_agent, agent_id, agent_alias_id

sql_agent, agent_id, agent_alias_id = initialize_agent()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Your prompt:"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if sql_agent and agent_id and agent_alias_id:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            try:
                response = sql_agent.invoke_agent(agent_id, agent_alias_id, prompt)
                for event in response['completion']:
                    if 'chunk' in event:
                        chunk = event['chunk']['bytes'].decode('utf-8')
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    elif 'trace' in event:
                        logger.info(f"Trace: {json.dumps(event['trace'], indent=2)}")
                message_placeholder.markdown(full_response)
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                logger.error(f"An error occurred: {str(e)}")
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})

# Sidebar for logs
st.sidebar.title("Logs")
logs = log_stream.getvalue()
st.sidebar.text_area("Application Logs", value=logs, height=300, key="log_area")