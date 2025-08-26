#!/usr/bin/env python3
"""
Quick start script for the Grad Director AI Chatbot
"""

import streamlit as st
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.chat_history import InMemoryChatMessageHistory

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Grad Director AI Chatbot",
    page_icon="",
    layout="centered"
)

def initialize_session_state():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = InMemoryChatMessageHistory()

# Initialize session state
initialize_session_state()

# Initialize LangChain components
@st.cache_resource
def get_llm():
    """Initialize the language model with GPT-4"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("❌ OPENAI_API_KEY not found in .env file")
        st.info("Please create a .env file in the project root with: OPENAI_API_KEY=your_api_key_here")
        st.stop()
    
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        openai_api_key=api_key
    )

# Main app interface
def main():

    st.title("Grad Director AI Chatbot")
    st.markdown("---")
    
    # Check API key first
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("❌ OPENAI_API_KEY not found in .env file")
        st.info("""
        **To fix this:**
        1. Create a `.env` file in the project root
        2. Add your OpenAI API key: `OPENAI_API_KEY=your_api_key_here`
        3. Get your API key from: https://platform.openai.com/api-keys
        """)
        st.stop()
    
    # Clear chat button in main area
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.session_state.chat_history = InMemoryChatMessageHistory()
            st.rerun()
    
    with col2:
        st.markdown("Start chatting below! You can ask questions about graduate programs, admissions, requirements, and academic guidance. You can also ask about the application process, deadlines, and other relevant information.")
    
    st.markdown("---")
    
    # Main chat area
    chat_container = st.container()
    
    with chat_container:
        # Display chat messages
        if "messages" in st.session_state:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        
        # Chat input
        if user_response := st.chat_input("What would you like to know?"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": user_response})
            st.session_state.chat_history.add_message(HumanMessage(content=user_response))
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(user_response)
            
            # Get AI response
            with st.chat_message("assistant"):
                with st.spinner("🤔 Thinking..."):
                    try:
                        # Get LLM
                        llm = get_llm()
                        
                        if llm is None:
                            st.error("Failed to initialize the language model.")
                            return
                        
                        # Create messages with system preamble
                        system_message = SystemMessage(content="You are a helpful grad director chatbot. You help students with questions about graduate programs, admissions, requirements, and academic guidance.")
                        
                        # Get response from LLM with system message and chat history
                        messages = [system_message] + st.session_state.chat_history.messages + [HumanMessage(content=user_response)]
                        response = llm.invoke(messages)
                        
                        # Display AI response
                        st.markdown(response.content)
                        
                        # Add AI message to chat history
                        st.session_state.messages.append({"role": "assistant", "content": response.content})
                        st.session_state.chat_history.add_message(AIMessage(content=response.content))
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        st.info("Please check your API key and internet connection.")

if __name__ == "__main__":
    main()
