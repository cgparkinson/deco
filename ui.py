import streamlit as st
import replicate
from planner import make_dive_graph_from_command_list

def format_message_history(messages):
    def format_message(message):
        if message["role"] == "user":
            return f"[INST] {message['content']} [/INST]"
        else:
            return message["content"]
    return '\n'.join([format_message(message) for message in messages])

first_prompt = {"role": "user", "content": """
You are a chatbot designed to help plan SCUBA dives. Your response will always be a human-readable, friendly response of no more than 20 words, followed by a dive plan in a command format. The human-readable response must never reference the commands. The command format has the following commands available:

START DIVE
END DIVE
CHANGE DEPTH TO x, SPEED DEFAULT
CONSTANT DEPTH x MIN

Here are some examples.

EXAMPLE 1

I want to dive to 30 metres. I'll first descend to 30 metres and stay there for 10 minutes. Then I'll go to 20 metres and stay there for 5 minutes. Then I'll go to 5 metres and stay there for 3 minutes.

RESULT 1
Sure, here's a dive plan that meets your needs!

COMMANDS:
START DIVE
CHANGE DEPTH TO 30, SPEED DEFAULT
CONSTANT DEPTH 10 MIN
CHANGE DEPTH TO 20, SPEED DEFAULT
CONSTANT DEPTH 5 MIN
CHANGE DEPTH TO 5, SPEED DEFAULT
CONSTANT DEPTH 3 MIN
CHANGE DEPTH TO 0, SPEED DEFAULT
END DIVE

EXAMPLE 2

I want to dive to 40 metres. I'll first descend to 30 metres and stay there for 2 minutes. Then I'll go to 40 metres and stay there for 5 minutes. Then I'll go to 5 metres and stay there for 3 minutes.

RESULT 2
Sounds like a great dive! Here's how that looks.
COMMANDS:
START DIVE
CHANGE DEPTH TO 30, SPEED DEFAULT
CONSTANT DEPTH 2 MIN
CHANGE DEPTH TO 40, SPEED DEFAULT
CONSTANT DEPTH 5 MIN
CHANGE DEPTH TO 5, SPEED DEFAULT
CONSTANT DEPTH 3 MIN
CHANGE DEPTH TO 0, SPEED DEFAULT
END DIVE"""}

st.title("Deco's Planner")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "avatar": "🐱", "content": "Hi, I'm Deco! Emil and Elin left, so I had to get a job. I can help plan your dives! Let's get started with some info like: how deep do you want to go, and for how long? \n Please give me about 20 seconds to answer your first message."}]

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=message["avatar"]):
        st.markdown(message["content"])

def strip_commands_from_response(full_response):
    if 'COM' in full_response:
        printed_response = full_response
        printed_response = printed_response.replace('COMMANDS', '<SPLIT>')
        printed_response = printed_response.replace('END DIVE', '<SPLIT>')
        printed_response = printed_response.split('<SPLIT>')
        if len(printed_response) == 2:
            printed_response = printed_response[0]
        else:
            printed_response = ''.join([printed_response[0], printed_response[2]])
            # st.pyplot(make_dive_graph_from_command_list(printed_response[1]))
    else:
        printed_response = full_response
    return printed_response

# Accept user input
if prompt := st.chat_input("What is up?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    printing_commands = False
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant", avatar='🐱'):
        message_placeholder = st.empty()
        full_response = ""
        for chunk in replicate.stream(
            # The mistralai/mistral-7b-instruct-v0.2 model can stream output as it's running.
            # "mistralai/mistral-7b-instruct-v0.2",
            "meta/llama-2-13b-chat",
            input={
                "prompt": format_message_history([first_prompt] + st.session_state.messages),
                "max_new_tokens": 256
            },
        ):
            full_response += str(chunk)
            if 'COM' in str(chunk):
                printing_commands = True
            if printing_commands and 'END DIVE' in full_response:
                printing_commands = False
            # Add a blinking cursor to simulate typing
            if not printing_commands:
                message_placeholder.markdown(strip_commands_from_response(full_response) + "▌")
        message_placeholder.markdown(strip_commands_from_response(full_response))
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response})
