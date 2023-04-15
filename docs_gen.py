import openai
import streamlit as st

st.set_page_config(
    layout="wide",
)

# openai.api_key = st.secrets["OPEN_AI_KEY"]
openai.api_key = "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"


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


def main():

    if "alltext" not in st.session_state:
        st.session_state["alltext"] = []

    instructions = """
    Let's think step by step
    """

    deep_text = """

    To achieve the best results with this task
    If you need additional information, please ask questions.
    """

    st.write("# 👨🏼‍🤝‍👨🏼Clone GPT ")

    with st.sidebar:
        inputtext = st.text_area("テキストを入力")
        deep = st.checkbox("Deep", help="情報が不足する場合、質問を返します。")

    if deep:
        instructions += deep_text

    if len(st.session_state["alltext"]) > 6:
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
            new_place.write(result_text)
        st.session_state["alltext"].append(f"\n### AI:\n {result_text}")


main()
