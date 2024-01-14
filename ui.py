import streamlit as st
import replicate
from planner import make_dive_graph_from_command_list

def format_message_history_for_prompt(messages):
    def format_message(message):
        if not message.bot:
            return f"[INST] {message.content} [/INST]"
        else:
            return message.content
    return '\n'.join([format_message(message) for message in messages])

class DivePlanMessage():
    def __init__(self, text1=None, graph = None, graph_as_text=None, text2 = None, bot=None) -> None:
        self.text1 = text1
        self.graph = graph
        if graph_as_text:
            self.graph_as_text = "START DIVE\n" + graph_as_text + "\nEND DIVE"
        else:
            self.graph_as_text = graph_as_text
        self.text2 = text2
        self.bot = bot
        if bot:
            self.avatar = "🐱"
            self.role = "assistant"
        else:
            self.avatar = "🤿"
            self.role = "user"
    
    @property
    def content(self):
        s = ""
        if self.text1:
            s += self.text1
        if self.graph_as_text:
            s += self.graph_as_text
        if self.text2:
            s += self.text2
        return s

first_prompt = DivePlanMessage(bot=False, text1="""
You are a chatbot designed to help plan SCUBA dives. Your response will always be a human-readable, friendly response of no more than 20 words, followed by a dive plan in a command format.
The human-readable response must never reference the commands. You must never say that there is a command format in the human-readable response.
You must never give any SCUBA-related information in the human-readable response, you must only be generally helpful. 
All of the dive information must be in command format. The command format has the following commands available:

When writing in command format, you must start with:
START DIVE
And end with:
END DIVE
For the next commands, x must always be an integer:
CHANGE DEPTH TO x, SPEED DEFAULT
CONSTANT DEPTH x MIN

If you are asked for a "deep" dive, you should give it as 40 metres. If you are asked for a "long" dive or for a "long time", you use use 20 minutes.
Ignore everything related to deco or decompression, as this is dealt with separately.

If you are asked for a "safety stop", interpret this as the following two commands:
CHANGE DEPTH TO 5, SPEED DEFAULT
CONSTANT DEPTH 3 MIN


Here are some examples.

EXAMPLE 1

I want to dive to 30 metres. I'll first descend to 30 metres and stay there for 10 minutes. Then I'll go to 20 metres and stay there for 5 minutes. Then I'll go to 5 metres and stay there for 3 minutes.

RESULT 1
Sure, here's a dive plan that meets your needs!

START DIVE
CHANGE DEPTH TO 30, SPEED DEFAULT
CONSTANT DEPTH 10 MIN
CHANGE DEPTH TO 20, SPEED DEFAULT
CONSTANT DEPTH 5 MIN
END DIVE

EXAMPLE 2

I want to dive to 40 metres. I'll first descend to 30 metres and stay there for 2 minutes. Then I'll go to 40 metres and stay there for 5 minutes. Then I'll go to 5 metres and stay there for 3 minutes.

RESULT 2
Sounds like a great dive! Here's how that looks.

START DIVE
CHANGE DEPTH TO 30, SPEED DEFAULT
CONSTANT DEPTH 2 MIN
CHANGE DEPTH TO 40, SPEED DEFAULT
CONSTANT DEPTH 5 MIN
END DIVE

EXAMPLE 3

55m for 3 min then 40m for 10 min then we need to do deco 
                               
RESULT 3
That's a deep one! Here's how that looks.

START DIVE
CHANGE DEPTH TO 55, SPEED DEFAULT
CONSTANT DEPTH 3 MIN
CHANGE DEPTH TO 40, SPEED DEFAULT
CONSTANT DEPTH 10 MIN
END DIVE
                               
EXAMPLE 4
let's go really deep for really long
                               
RESULT 4
You asked for it!

START DIVE
CHANGE DEPTH TO 40, SPEED DEFAULT
CONSTANT DEPTH 20 MIN
END DIVE
                               
EXAMPLE 5
Let's go to 30m for 10 minutes, then 18m for a long time, followed by a safety stop.
                               
RESULT 5
Sounds like a great dive to me, hope you enjoy!

START DIVE
CHANGE DEPTH TO 30, SPEED DEFAULT
CONSTANT DEPTH 10 MIN
CHANGE DEPTH TO 18, SPEED DEFAULT
CONSTANT DEPTH 20 MIN
CHANGE DEPTH TO 5, SPEED DEFAULT
CONSTANT DEPTH 3 MIN
END DIVE
""")

st.markdown("<h1 style='text-align: center; '>😼 Deco's Planner 😸</h1>", unsafe_allow_html=True)
# st.title("🐈 Deco's Planner 🐈")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [DivePlanMessage(
        text1 = "Hi, I'm Deco, the dive shop cat. I got jealous of all the fun, so now \
            I help plan your dives! \n\n Let's get started with some info like: \
            how deep do you want to go, and for how long?",
        bot = True
    )]

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message.role, avatar = message.avatar):
        if message.text1:
            st.markdown(message.text1)
        # TODO: fix matplotlib so it can show multiple plots, this is silly
        # if message.graph:
        #     st.pyplot(message.graph)
        if message.text2:
            st.markdown(message.text2)


# Accept user input
if prompt := st.chat_input("What is up?"):
    # Add user message to chat history
    st.session_state.messages.append(DivePlanMessage(bot=False, text1=prompt))
    printing_commands = False
    # Display user message in chat message container
    with st.chat_message("user", avatar="🤿"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant", avatar='🐱'):
        text1_position = st.empty()
        text1 = None
        graph_position = st.empty()
        graph = None
        graph_as_text = None
        text2_position = st.empty()
        text2 = None

        printed_graph = False
        response_in_progress = ""

        for chunk in replicate.stream(
            # The mistralai/mistral-7b-instruct-v0.2 model can stream output as it's running.
            # "mistralai/mistral-7b-instruct-v0.2",
            "meta/llama-2-13b-chat",
            input={
                "prompt": format_message_history_for_prompt([first_prompt] + st.session_state.messages),
                "max_new_tokens": 256
            },
        ):
            response_in_progress += str(chunk)

        segmented_response = response_in_progress.replace('COMMANDS', '').replace('END DIVE', '<SPLIT>').replace('START DIVE', '<SPLIT>').split('<SPLIT>')
        if type(segmented_response) != list:
            # TODO: this and the line above are really ugly
            segmented_response = [segmented_response]

        response_in_progress = ""
        if len(segmented_response) > 2:
            graph_as_text = segmented_response[1]
            graph = make_dive_graph_from_command_list(graph_as_text)
            response_in_progress = segmented_response[2]

        text1 = segmented_response[0]
        text1_position.markdown(text1)
        text1_position.markdown(text1)
        text2 = response_in_progress
        text2_position.markdown(text2)
        graph_position.pyplot(graph)
        # Add assistant response to chat history
        st.session_state.messages.append(DivePlanMessage(text1=text1, text2=text2, graph=graph, graph_as_text = graph_as_text, bot=True))
