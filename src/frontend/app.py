import streamlit as st
import uuid
from agents.vct_agent import process_vct_query_sync

# Streamlit app
st.title("Valorant Esports Manager Chatbot")

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.user_id = "user123"

# Display session information
st.sidebar.title("Session Information")
st.sidebar.write(f"Session ID: {st.session_state.session_id}")
st.sidebar.write(f"User ID: {st.session_state.user_id}")

# Chat input
user_input = st.text_input("You:", key="user_input")

if st.button("Send"):
    if user_input:
        # Process the query
        result = process_vct_query_sync(user_input, st.session_state.user_id, st.session_state.session_id)
        
        # Display results
        st.write("\nMetadata:")
        st.write(f"Selected Agent: {result['agent_name']}")
        st.write(f"Is Streaming: {result['is_streaming']}")
        st.write(f"Response: {result['content']}")

        # Clear the input box
        st.session_state.user_input = ""