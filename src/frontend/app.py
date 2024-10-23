import streamlit as st
import asyncio
from agents.vct_agent import VCTAgentSystem
from st_chat_message import message
import time

def init_session_state():
    """Initialize session state variables if they don't exist"""
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

def get_unique_key():
    """Generate a unique key for messages"""
    st.session_state.message_counter += 1
    return f"msg_{int(time.time())}_{st.session_state.message_counter}"

async def initialize_agent():
    """Initialize the VCTAgentSystem"""
    try:
        if st.session_state.agent_system is None:
            vct_system = VCTAgentSystem()
            await vct_system.switch_to_anthropic_classifier()
            st.session_state.agent_system = vct_system
    except Exception:
        st.error("There was an error initializing the chat. Please refresh the page and try again.")
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
    
    # Create three columns with the middle one taking 70% of the width
    left_col, middle_col, right_col = st.columns([0.05, 0.9, 0.05])
    
    # Add minimal CSS to only handle the chat message area
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
        
        /* Add spacing between messages */
        .stChatMessage {
            margin-bottom: 1rem;
        }

        .stBottom{
            width: 85% !important;
            max-width: 85%;
        }
        
        /* Ensure messages container doesn't overlap with input */
        [data-testid="column"] {
            padding-bottom: 5rem;
        }

        /* Control image sizes in markdown */
        .element-container img {
            max-width: 300px !important;  /* Adjust this value as needed */
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
        
        /* Make messages visible */
        .element-container {
            overflow: visible !important;
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
            msg_key = msg.get("key", get_unique_key())
            if "key" not in msg:
                msg["key"] = msg_key
            message(msg["content"], is_user=is_user, key=msg_key)
    
    # Chat input (using Streamlit's default positioning)
    if prompt := st.chat_input("Ask me anything about Valorant esports...", key="chat_input"):
        # Generate a unique key for the new message
        user_msg_key = get_unique_key()
        
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt,
            "key": user_msg_key
        })
        
        with middle_col:
            message(prompt, is_user=True, key=user_msg_key)
            
            # Get and display assistant response
            with st.spinner("Thinking..."):
                result = asyncio.run(process_message(prompt))
                response_content = result.get('content', 'There was an error processing your message. Please refresh the page and try again.')
                
                assistant_msg_key = get_unique_key()
                message(response_content, is_user=False, key=assistant_msg_key)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_content,
                    "key": assistant_msg_key
                })

if __name__ == "__main__":
    main()