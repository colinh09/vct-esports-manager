import streamlit as st
import asyncio
from agents.vct_agent import VCTAgentSystem
from st_chat_message import message  # Import the new component

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

async def initialize_agent():
    """Initialize the VCTAgentSystem"""
    if st.session_state.agent_system is None:
        vct_system = VCTAgentSystem()
        await vct_system.switch_to_anthropic_classifier()
        st.session_state.agent_system = vct_system

async def process_message(prompt):
    """Process a message and return the response"""
    try:
        result = await st.session_state.agent_system.process_query(
            prompt,
            st.session_state.user_id,
            st.session_state.session_id
        )
        return result
    except Exception as e:
        st.error(f"Error processing message: {str(e)}")
        return {"content": "Sorry, I encountered an error processing your message."}

def main():
    st.set_page_config(page_title="VCT Agent Chat", layout="wide")
    
    # Initialize session state
    init_session_state()
    
    # Create three columns with the middle one taking 70% of the width
    left_col, middle_col, right_col = st.columns([0.15, 0.7, 0.15])
    
    # Add CSS to keep chat input at bottom and center the title
    st.markdown(
        """
        <style>
            h1 {
                text-align: center;
            }
            section[data-testid="stSidebar"] {
                width: 0px;
            }
            .stBottom {
                bottom: 0;
                position: fixed;
                left: 50%;
                transform: translateX(-50%);
                width: 70% !important;
                max-width: 70%;
            }
            .main {
                padding-bottom: 80px;
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
        
        # Display chat messages using the new component
        for msg in st.session_state.messages:
            is_user = msg["role"] == "user"
            message(msg["content"], is_user=is_user)
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about Valorant esports..."):
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        with middle_col:
            message(prompt, is_user=True)
            
            # Get and display assistant response
            with st.spinner("Thinking..."):
                result = asyncio.run(process_message(prompt))
                response_content = result.get('content', 'No response available')
                message(response_content, is_user=False)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_content
                })

if __name__ == "__main__":
    main()