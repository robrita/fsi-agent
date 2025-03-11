import pandas as pd
import streamlit as st
import numpy as np
import json

from datetime import datetime
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project_client = AIProjectClient.from_connection_string(
    conn_str=st.session_state.project_connection, credential=DefaultAzureCredential()
)

# Set the page title
st.header("AI Agent List")

if "json_data" not in st.session_state:
    with st.spinner("Fetching data..."):
        # Load the agents from the project client
        json_data = project_client.agents.list_agents()
        st.session_state.json_data = json_data['data']

# Extract the data part and convert to pandas DataFrame
df = pd.DataFrame(st.session_state.json_data)

# Process the DataFrame to make it more readable
def format_created_at(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

df['created_at'] = df['created_at'].apply(format_created_at)

# Determine if tools are being used
df['has_tools'] = df['tools'].apply(lambda x: len(x) > 0)

# Select columns to display
display_columns = ['name', 'model', 'created_at', 'temperature', 'has_tools', 'id']
df_display = df[display_columns]

# Display the DataFrame
st.dataframe(df_display, use_container_width=True)

# Add details section
st.subheader("Agent Details")
selected_agent = st.selectbox("Select an agent to view details:", df['name'].tolist())

if selected_agent:
    agent_data = df[df['name'] == selected_agent].iloc[0]
    
    # Convert agent data to key-value pairs for DataFrame
    details = []
    for key, value in agent_data.items():
        # Always convert the final value to string to ensure Arrow compatibility
        if key == 'tools':
            if len(value) > 0:
                tools_list = [tool['type'] for tool in value]
                value = ', '.join(tools_list)
            else:
                value = "None"
        elif isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2)
        else:
            # Convert any type to string
            value = str(value)
        
        details.append({"Property": key, "Value": value})
    
    # Create and display DataFrame - with all string values
    details_df = pd.DataFrame(details)
    st.dataframe(details_df, use_container_width=True, height=600)
