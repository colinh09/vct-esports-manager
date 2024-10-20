import streamlit as st
import logging
import json
from io import StringIO
import sys
from datetime import datetime

sys.path.append('..')
from agents.parser_agent import VctInputParserAgent
from utils.aws_utils import check_aws_permissions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
log_stream = StringIO()
logging_handler = logging.StreamHandler(log_stream)
logger.addHandler(logging_handler)

# Set page config
st.set_page_config(page_title="Valorant Esports Manager", page_icon="🎮", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .main {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .stButton>button {
        background-color: #FF4B4B;
        color: #FAFAFA;
    }
    .user-message {
        background-color: #262730;
        color: #FAFAFA;
        padding: 10px;
        border-radius: 15px;
        margin-bottom: 10px;
    }
    .assistant-message {
        background-color: #FF4B4B;
        color: #FAFAFA;
        padding: 10px;
        border-radius: 15px;
        margin-bottom: 10px;
    }
    .stTextInput>div>div>input {
        background-color: #262730;
        color: #FAFAFA;
    }
</style>
""", unsafe_allow_html=True)

# Initialize VctInputParserAgent and get agent details
@st.cache_resource
def initialize_agent():
    check_aws_permissions()
    parser_agent = VctInputParserAgent()
    agent_id, agent_alias_id = parser_agent.get_agent()
    if not agent_id or not agent_alias_id:
        st.error("Failed to get agent. Please check your AWS permissions and try again.")
        return None, None, None
    return parser_agent, agent_id, agent_alias_id

# Sidebar
st.sidebar.image("https://placekitten.com/200/200", width=200)  # Replace with your logo
st.sidebar.title("Valorant Esports Manager")
st.sidebar.markdown("---")

# Display current date and time
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.sidebar.write(f"Current Time: {current_time}")

# Logs in sidebar
st.sidebar.subheader("Application Logs")
logs = log_stream.getvalue()
st.sidebar.text_area("Recent Logs", value=logs, height=300, key="log_area", disabled=True)

# Main content
st.title("🎮 Valorant Esports Manager Chatbot")
st.markdown("Welcome to your personal Valorant Esports assistant. How can I help you today?")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        message_class = "user-message" if message["role"] == "user" else "assistant-message"
        st.markdown(f'<div class="{message_class}">{message["content"]}</div>', unsafe_allow_html=True)

# Chat input
prompt = st.text_input("Your message:", key="user_input")
if st.button("Send"):
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        parser_agent, agent_id, agent_alias_id = initialize_agent()
        
        if parser_agent and agent_id and agent_alias_id:
            with st.spinner("Thinking..."):
                try:
                    response = parser_agent.invoke_agent(prompt, agent_alias_id)
                    full_response = ""
                    for event in response['completion']:
                        if 'chunk' in event:
                            chunk = event['chunk']['bytes'].decode('utf-8')
                            full_response += chunk
                        elif 'trace' in event:
                            logger.info(f"Trace: {json.dumps(event['trace'], indent=2)}")
                    
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    logger.error(f"An error occurred: {str(e)}")
        
        # Clear input after sending
        st.session_state.user_input = ""
        
        # Rerun to update chat display
        st.experimental_rerun()

# Footer
st.markdown("---")
st.markdown("Powered by Streamlit | © 2024 Valorant Esports Manager")