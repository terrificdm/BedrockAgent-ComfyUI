import uuid
import json
import os
import requests
import boto3
import streamlit as st


boto3_session = boto3.session.Session()
bedrock_agent_runtime_client = boto3_session.client("bedrock-agent-runtime")
lambda_client = boto3_session.client('lambda')

# Load parameters from local file
with open('/tmp/parameter.json', "r") as file:
    json_parameters = file.read()
parameters = json.loads(json_parameters)
agent_id = parameters["agent_id"]
agent_alias_id = parameters["agent_alias_id"]
function_name = parameters["function_name"]

# Create a folder to prepare saving created images
images_folder = "./output_image"
os.makedirs(images_folder, exist_ok=True)

session_id = str(uuid.uuid1())

# App title
st.set_page_config(page_title="BedrockAgent-ImageCreator 💬")

if 'parameter' not in st.session_state:
    st.session_state['parameter'] = ''

def update_lambda_env(endpoint, workflow):
    configuration = {
        'FunctionName': function_name,
        'Environment': {
            'Variables': {}
        }
    }
    
    # Get current Lambda Variables
    response = lambda_client.get_function_configuration(FunctionName=function_name)
    current_variables = response['Environment']['Variables']
    
    # Update Variables of configuration with current Lambda Variables
    configuration['Environment']['Variables'].update(current_variables)
    
    session_state_parameter = None

    if endpoint:
        configuration['Environment']['Variables']['server_address'] = endpoint
        session_state_parameter = 'Comfyui endpoint'

    if workflow:
        workflow = workflow.read().decode('utf-8')
        configuration['Environment']['Variables']['prompt_text'] = workflow
        if session_state_parameter:
            session_state_parameter = 'Comfyui endpoint and Comfyui api workflow'
        else:
            session_state_parameter = 'Comfyui api workflow'

    lambda_client.update_function_configuration(**configuration)

    if session_state_parameter:
        st.session_state['parameter'] = session_state_parameter
    
def clear_history():
    st.session_state.messages = []
    st.empty()
    session_id = str(uuid.uuid1())

def create_image(input_text):
    response = bedrock_agent_runtime_client.invoke_agent(inputText=input_text,
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
    )
    event_stream = response['completion']
    for event in event_stream:
        if 'chunk' in event:
            output_data = event['chunk']['bytes'].decode('utf8')
    return output_data 
                
with st.sidebar:
    st.title('ImageCreator Chatbot🎈')
    st.markdown("""
    ### **Behind the chatbot:**  
    Based on your inputs, Bedrock Claude will extract image description then enrich and rewrite it into a Stable Diffusion prompt. After that, it will automatically call Comfyui by leveraging Bedrock Agent to generate an image for you""")
    with st.expander('Comfyui Configurations', expanded=False):
        endpoint = st.text_input('Comfyui endpoint', "")
        workflow = st.file_uploader("Comfyui api workflow json file")
        if endpoint or workflow:
            response = st.button("Submit", on_click=update_lambda_env, args=[endpoint, workflow])
            if response:
                st.write(st.session_state['parameter']+" updated!")
        else:
            st.button("Submit", disabled=True)    
    st.sidebar.button("Clear history", type="primary", on_click=clear_history)
    st.markdown("""
    > User inputs can be any language, but eventually, a generated prompt for Stable Diffusion will be English
    
    > The best input for creating images is providing image description directly, if you provide irrelevant, Claude will ask you for more input, it may cause some confusions, such as prompt not always English, prompt is not enriched, still needs more PE
    """)

with st.chat_message("assistant"):
    st.write("Welcome👋👋👋, tell me what image you need？💬")    
    
# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    
# Display chat messages from history on app rerun
for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    else:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], str):
                st.markdown(message["content"])
            else:
                for key, value in message["content"].items():
                    caption = key
                    for image_url in value:
                        image_name = image_url.split("filename=")[1].split("&")[0]
                        save_path = os.path.join(images_folder, image_name)
                        st.image(save_path, caption=caption, output_format="JPEG")
                        
# React to user input
if query := st.chat_input("Provide image descripiton here:"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": query})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(query)
    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        with st.spinner('A moment please...'):
            output_data = create_image(query)
            if "view?filename=" in output_data:
                output_data = json.loads(output_data)
                for key, value in output_data.items():
                    caption = key
                    for image_url in value:
                        image_name = image_url.split("filename=")[1].split("&")[0]
                        # Send Http request and save image
                        response = requests.get(image_url)
                        if response.status_code == 200:
                            save_path = os.path.join(images_folder, image_name)
                            with open(save_path, "wb") as file:
                                file.write(response.content)
                                st.image(save_path, caption=caption, output_format="JPEG")
            else:
                st.markdown(output_data)
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": output_data})
