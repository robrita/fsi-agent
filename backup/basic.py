import streamlit as st
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure OpenAI Configuration
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "temperature" not in st.session_state:
    st.session_state.temperature = 0.7

# Main UI
st.header("💬 Financial Services AI Assistant")

# Display chat messages
for message in st.session_state.messages:
    if message["role"] == "user":
        st.chat_message(message["role"], avatar=":material/person:").markdown(message["content"])
    else:
        st.chat_message(message["role"], avatar="✨").markdown(message["content"])

def generate_response():
    """Generate response from Azure OpenAI"""
    try:
        # Prepare messages for API call
        messages = [{"role": "system", "content": "You are a helpful AI assistant."}]
        
        # Include conversation history
        for msg in st.session_state.messages:
            messages.append(msg)

        # Call Azure OpenAI API
        with st.spinner("Thinking..."):
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=800
            )

        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
        return "I'm sorry, I encountered an error while processing your request."

# User input
if prompt := st.chat_input("Type your message here..."):    
    # Display user message immediately
    st.chat_message("user", avatar=":material/person:").markdown(prompt)

    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Generate and show AI response
    with st.chat_message("assistant", avatar="✨"):
        message_placeholder = st.empty()
        response = generate_response()
        message_placeholder.markdown(response)
    
    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": response})
