import streamlit as st
import asyncio
from agents.vct_agent import VCTAgentSystem
import time
import os

def init_session_state():
    """Initialize session state variables if they don't exist"""
    os.environ['RDS_DATABASE_URL'] = st.secrets["RDS_DATABASE_URL"]

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent_system" not in st.session_state:
        st.session_state.agent_system = None
    if "user_id" not in st.session_state:
        st.session_state.user_id = "streamlit_user"
    if "session_id" not in st.session_state:
        st.session_state.session_id = "streamlit_session"
    if "message_counter" not in st.session_state:
        st.session_state.message_counter = 0
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

def check_password():
    """Returns True if the password is correct"""
    if st.session_state.authenticated:
        return True
    
    # Create a container for the password section
    with st.container():
        # Only show password input if not authenticated
        if not st.session_state.authenticated:
            st.markdown(
                """
                # 👋 Welcome to the VCT Chat Assistant!
                
                🔒 If you are a judge for the VCT Hackathon:
                The password was provided in my submission details.
                It can be obtained by the "upload a file" section!
                
                🚫 If you are not a judge:
                This is a private application built for the VCT Hackathon.
                """
            )
            
            password_input = st.text_input("Please enter the password:", type="password")
            
            if password_input:
                if password_input == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()  # Rerun the app to clear the password section
                else:
                    st.error("Incorrect password. Please try again.")
                    return False
            return False
    
    return True

def get_unique_key():
    """Generate a unique key for messages"""
    st.session_state.message_counter += 1
    return f"msg_{int(time.time())}_{st.session_state.message_counter}"

async def initialize_agent():
    """Initialize the VCTAgentSystem"""
    try:
        if st.session_state.agent_system is None:
            vct_system = VCTAgentSystem(
                st.secrets["AWS_ACCESS_KEY"],
                st.secrets["AWS_SECRET_ACCESS_KEY"],
                st.secrets["ANTHROPIC_API_KEY"],
                st.secrets["AWS_DEFAULT_REGION"]
            )
            await vct_system.initialize()
            st.session_state.agent_system = vct_system
    except Exception as e:
        st.error(f"There was an error initializing the chat: {str(e)}")
        return None

async def process_message(prompt):
    """Process a message and return the response"""
    try:
        result = await st.session_state.agent_system.process_query(
            prompt,
            st.session_state.user_id,
            st.session_state.session_id
        )
        return result
    except Exception:
        return {"content": "There was an error processing your message. Please refresh the page and try again."}

def main():
    st.set_page_config(page_title="VCT Agent Chat", layout="wide")
    
    # Initialize session state
    init_session_state()
    
    # Check password before showing anything else
    if not check_password():
        return
        
    # Create three columns with the middle one taking 70% of the width
    left_col, middle_col, right_col = st.columns([0.05, 0.9, 0.05])
    
    # Add CSS to handle styling
    st.markdown(
        """
        <style>
        /* Center title */
        h1 {
            text-align: center;
            margin-bottom: 2rem;
        }

        /* Hide default sidebar */
        section[data-testid="stSidebar"] {
            width: 0px;
        }

        /* Style chat messages */
        [data-testid="stChatMessage"] {
            margin-bottom: 1rem;
            font-size: 24px !important;
        }

        .stBottom {
            width: 85% !important;
            max-width: 85%;
        }

        /* Ensure messages container doesn't overlap with input */
        [data-testid="column"] {
            padding-bottom: 5rem;
        }

        /* Control image sizes in markdown */
        .element-container img {
            max-width: 300px !important;
            height: auto !important;
            display: inline-block !important;
        }

        /* Style for markdown tables */
        table {
            width: auto !important;
            margin: 0 auto;
        }

        td {
            padding: 5px !important;
            text-align: center !important;
        }

        /* Remove scrollbars and fix message display */
        [data-testid="stChatMessage"], 
        [data-testid="stChatMessage"] > div,
        .stMarkdown,
        [data-testid="stMarkdownContainer"] {
            overflow: visible !important;
            max-height: none !important;
            height: auto !important;
        }

        /* Ensure content wraps properly */
        [data-testid="stChatMessage"] p {
            white-space: pre-wrap !important;
            word-wrap: break-word !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    with middle_col:
        # Set up the main title
        st.title("VCT Agent Chat")
        
        # Initialize the agent system
        asyncio.run(initialize_agent())
        
        # Display chat messages
        for msg in st.session_state.messages:
            is_user = msg["role"] == "user"
            with st.chat_message("user" if is_user else "assistant"):
                st.write(msg["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about Valorant esports...", key="chat_input"):
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt
        })
        
        with middle_col:
            # Display user message
            with st.chat_message("user"):
                st.write(prompt)
            
            # Get and display assistant response
            with st.spinner("Thinking..."):
                result = asyncio.run(process_message(prompt))
                response_content = result.get('content', 'There was an error processing your message. Please refresh the page and try again.')
                
                with st.chat_message("assistant"):
                    st.write(response_content)
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_content
                })

if __name__ == "__main__":
    main()