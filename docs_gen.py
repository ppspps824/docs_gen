import openai
import streamlit as st
from plantweb.render import render

st.set_page_config(page_title="Clone GPT", page_icon="👨🏼‍🤝‍👨🏼", layout="wide")

try:
    openai.api_key = st.secrets["OPEN_AI_KEY"]
except:
    pass


def chat(text, messages=None, settings="", max_tokens=1000):

    # やり取りの管理
    messages = messages if messages is not None else []
    if settings and not messages:
        messages.append({"role": "system", "content": settings})
    messages.append({"role": "user", "content": text})

    # APIを叩く、streamをTrueに
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
    )

    # 返答を受け取り、逐次yield
    for chunk in resp:
        if chunk:
            content = chunk["choices"][0]["delta"].get("content")
            if content:
                yield content


def get_graph_text(text):
    result = ""
    st = text.find("digraph")
    end = text.find("}")
    result = text[st : end + 1]

    return result


def get_uml_text(text):
    result = ""
    st = text.find("@startuml")
    end = text.find("@enduml")

    umltext = text[st : end + 7]

    if umltext:
        result = render(
            umltext,
            engine="plantuml",
            format="png",
            cacheopts={"use_cache": False},
        )
        make = True
    else:
        make = False

    return result, make


def main():
    hide_streamlit_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                </style>
                """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    if "alltext" not in st.session_state:
        st.session_state["alltext"] = []

    instructions = """
    Let's think step by step
    To achieve the best results with this task
    If you need additional information, please ask questions.
    Answer in Japanese.
    """

    st.write("# 👨🏼‍🤝‍👨🏼Clone GPT ")

    with st.sidebar:
        inputtext = st.text_area("テキストを入力")
        image_url = st.text_input("画像のURLを入力")
        if image_url:
            st.image(image_url, use_column_width="always")

    if image_url:
        instructions += f"\n ![source]({image_url})"

    if len(st.session_state["alltext"]) > 10:
        del st.session_state["alltext"][0:1]

    if inputtext:
        st.session_state["alltext"].append(f"\n#### You:\n{inputtext}")

        result_text = ""
        message = "\n".join(st.session_state["alltext"])
        old_place = st.empty()
        old_place.write(message)
        st.write("#### AI:")
        new_place = st.empty()

        for talk in chat(
            message,
            settings=instructions,
        ):
            result_text += talk
            clean_text = result_text.replace("#", "").replace("AI:\n", "")
            new_place.write(clean_text)
        st.session_state["alltext"].append(f"\n#### AI:\n {clean_text}")

        graphtext = get_graph_text(result_text)
        umltext, make = get_uml_text(result_text)

        if graphtext:
            st.graphviz_chart(graphtext)

        if make:
            st.image(umltext[0])


main()
