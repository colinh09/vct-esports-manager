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
    
    # Create three columns with the middle one taking 70% of the width
    left_col, middle_col, right_col = st.columns([0.05, 0.9, 0.05])
    
    # Add CSS and JavaScript to handle styling and prevent auto-scrolling
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
        .stChatMessage, 
        .stChatMessage > div,
        .stMarkdown,
        [data-testid="stMarkdownContainer"] {
            overflow: visible !important;
            max-height: none !important;
            height: auto !important;
        }

        /* Ensure content wraps properly */
        .stChatMessage p {
            white-space: pre-wrap !important;
            word-wrap: break-word !important;
        }

        /* Disable smooth scrolling behavior */
        * {
            scroll-behavior: auto !important;
        }
        </style>
        <script>
            // Disable Streamlit's automatic scrolling
            const disableAutoScroll = () => {
                const style = document.createElement('style');
                style.textContent = `
                    .main > div { scroll-behavior: auto !important; }
                    .element-container { scroll-margin-top: 0 !important; }
                `;
                document.head.appendChild(style);
                
                // Override Streamlit's scroll function
                if (window.ScrollIntoViewObserver) {
                    window.ScrollIntoViewObserver.prototype.observe = function() {};
                    window.ScrollIntoViewObserver.prototype.disconnect = function() {};
                }
            };
            
            // Run once DOM is loaded
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', disableAutoScroll);
            } else {
                disableAutoScroll();
            }
        </script>
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
            if is_user:
                message(msg["content"],
                    is_user=True,
                    key=msg_key,
                    logo="https://api.dicebear.com/9.x/thumbs/svg?seed=Nolan&backgroundColor=69d2e7,b6e3f4,c0aede,d1d4f9,f1f4dc,f88c49,ffd5dc,ffdfbf&backgroundType=gradientLinear&eyes=variant2W16,variant3W10,variant3W12,variant3W14,variant3W16,variant4W10,variant4W12,variant4W14,variant4W16,variant5W10,variant5W12,variant5W14,variant5W16,variant6W10,variant6W12,variant6W14,variant6W16,variant7W10,variant7W12,variant7W14,variant7W16,variant8W10,variant8W12,variant8W14,variant8W16,variant9W10,variant9W12,variant9W14,variant9W16&mouth=variant1,variant2,variant3,variant4&shapeColor=f1f4dc"
                    )
            else:
                message(msg["content"],
                    is_user=False,
                    key=msg_key,
                    logo="https://api.dicebear.com/9.x/bottts-neutral/svg?seed=Aidan&backgroundColor=e53935&eyes=eva"
                    )
    
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
            message(prompt, 
                   is_user=True, 
                   key=user_msg_key,
                   logo="https://api.dicebear.com/9.x/thumbs/svg?seed=Nolan&backgroundColor=69d2e7,b6e3f4,c0aede,d1d4f9,f1f4dc,f88c49,ffd5dc,ffdfbf&backgroundType=gradientLinear&eyes=variant2W16,variant3W10,variant3W12,variant3W14,variant3W16,variant4W10,variant4W12,variant4W14,variant4W16,variant5W10,variant5W12,variant5W14,variant5W16,variant6W10,variant6W12,variant6W14,variant6W16,variant7W10,variant7W12,variant7W14,variant7W16,variant8W10,variant8W12,variant8W14,variant8W16,variant9W10,variant9W12,variant9W14,variant9W16&mouth=variant1,variant2,variant3,variant4&shapeColor=f1f4dc"
                   )
            
            # Get and display assistant response
            with st.spinner("Thinking..."):
                result = asyncio.run(process_message(prompt))
                response_content = result.get('content', 'There was an error processing your message. Please refresh the page and try again.')
                
                assistant_msg_key = get_unique_key()
                message(response_content, 
                       is_user=False, 
                       key=assistant_msg_key,
                       logo="https://api.dicebear.com/9.x/bottts-neutral/svg?seed=Aidan&backgroundColor=e53935&eyes=eva"
                       )
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_content,
                    "key": assistant_msg_key
                })

if __name__ == "__main__":
    main()