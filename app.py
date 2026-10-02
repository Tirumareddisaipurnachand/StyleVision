import json

from google import genai
from google.genai import types
import streamlit as st

from twilio.rest import Client as TwilioClient


from prompts import SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE, SUMMARY_REQUEST_PROMPT

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]


@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key = GEMINI_API_KEY)

@st.cache_resource
def get_twilio_client():
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

twilio_client = get_twilio_client()
gemini_client = get_gemini_client()
MODEL_NAME = "gemini-3.8-flash"

def send_whatsapp(to_number, user_name, summary):
    try:
        content_variables = json.dumps(
            {
                "1": user_name,
                "2": clean_whatsapp_text(summary)
            },
            ensure_ascii=False
        )

        from_number = TWILIO_WHATSAPP_FROM.strip()
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        to_number = to_number.strip()
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        message = twilio_client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid=TWILIO_CONTENT_SID,
            content_variables=content_variables,
        )

        return True, message.sid

    except Exception as error:
        return False, str(error)

def clean_whatsapp_text(text):
    if not text:
        return "No nutrition summary available."
    text = " ".join(text.split())  # collapse whitespace/newlines
    return text[:1500] + "..." if len(text) > 1500 else text
 



def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.write(message["content"])
        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):
    st.session_state.messages.append({"role": role, "kind": kind, "content": content})
    render_message(st.session_state.messages[-1])

import time

def ask_gemini(parts):
    for attempt in range(4):
        try:
            response = st.session_state.chat.send_message(parts)
            return response.text

        except Exception as error:
            error_text = str(error)

            if "503" in error_text and attempt < 3:
                time.sleep(2 ** attempt)
                continue

            return "Gemini is temporarily busy. Please try again in a moment."


#step1: onboarding (username and phonenumber)

if 'onboarded' not in st.session_state:
    st.title("StyleVision 👔 ")
    st.caption("Your AI personal style assistant")

    with st.form("onboarding_form"):
        name = st.text_input("your name")
        whatsapp_number = st.text_input(
            "your whatsapp number (with country code)",
            placeholder = "+91xxxxxxxxxx",
            help = "the stylevision summary will be sent to this number.",
        )

        submitted = st.form_submit_button("let's style 😎")
    
    if submitted:
        if not name.strip() or not whatsapp_number.strip():
            st.warning("please fill in both fields to continue.")
        else:
            st.session_state.name = name.strip()
            st.session_state.whatsapp_number = whatsapp_number.strip()
            #activale my ai
            st.session_state.chat = gemini_client.chats.create(
                model = MODEL_NAME,
                config = types.GenerateContentConfig(system_instruction = SYSTEM_PROMPT),
            )
            st.session_state.messages = []
            st.session_state.onboarded = True
            st.rerun()
        
    st.stop()

# create a chat interface

header_col, button_col = st.columns([5, 2], vertical_alignment = "center")
with header_col:
    st.title("StyleVision 👔 ")

with button_col:
    send_disabled = len(st.session_state.messages) <= 1

    if st.button(
        "send style summary 🪡 to whatsapp",
        disabled=send_disabled,
        use_container_width=True
    ):
        with st.spinner("summarizing your style..."):
            summary = ask_gemini([SUMMARY_REQUEST_PROMPT])

            sucess, info = send_whatsapp(
                st.session_state.whatsapp_number,
                st.session_state.name,
                summary
            )

        if sucess:
            st.success("style summary sent to whatsapp successfully!")
        else:
            st.error(f"failed to send style summary to whatsapp: {info}")

st.caption(f"Logged in as {st.session_state.name} - updates go to {st.session_state.whatsapp_number}")

if not st.session_state.messages:
    add_message("assistant", "text", WELCOME_MESSAGE_TEMPLATE.format(name = st.session_state.name))
else:
    for message in st.session_state.messages:
        render_message(message)
            
user_input = st.chat_input(
    "Ask a question or add a picture of your outfit to get style advice",
accept_file = True,
file_type = ["png", "jpg", "jpeg"],
)

if user_input:
    photo = user_input.files[0] if user_input.files else None
    text = user_input.text
    parts = []

    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(types.Part.from_bytes(data = photo_bytes, mime_type = photo.type))
    if text:
        add_message("user", "text", text)
        parts.append(text)
    elif photo is not None:
        parts.append("what do you think of this outfit")
    with st.spinner("checking your style..."):
        answer = ask_gemini(parts)
    add_message("assistant", "text", answer)








