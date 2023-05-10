import openai
import streamlit as st
from plantweb.render import render
import time


def chat(text, settings, max_tokens, model):

    messages = [
        {"role": "system", "content": settings},
        {"role": "user", "content": text},
    ]

    # APIを叩く、streamをTrueに
    while True:
        error_count = 0
        try:
            resp = openai.ChatCompletion.create(
                model=model,
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
        except:
            if error_count < 3:
                time.sleep(3)
            else:
                st.error("エラーが発生しました。再実行すると解消する可能性があります。")
                st.stop


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
    if "alltext" not in st.session_state:
        st.session_state["alltext"] = []

    model = "gpt-4"

    st.write("# 📚LearnMateAI ")
    st.write("---")
    status_plasce = st.empty()

    with st.sidebar:
        with st.form("settings"):
            inputtext = st.text_input("テーマを入力")
            input_gen_length = st.number_input(
                "生成文字数を入力", min_value=0, step=100, help="0に設定すると指定なしとなります。"
            )
            submit = st.form_submit_button("生成開始")

    if submit:
        if input_gen_length:
            gen_length = f"- 文字数は必ず{input_gen_length}文字前後とする。これを守るために説明を省略しても構わない。"
        else:
            gen_length = ""

        instructions = f"""
あなたは{inputtext}におけるベテランの研修講師です。
{inputtext}について初学者～中級者が実務で通用するレベルで知識をつけられる研修資料を作成してください。
作成に当たっては以下に厳密に従ってください。特に文字数の指定には必ず従ってください。
- step by stepで複数回検討を行い、その中で一番優れていると思う結果を出力する。
- サンプルではなくそのまま利用できる品質とする。
- 説明の内容も省略しない。
- プログラミングやシェルなどコードを入力する内容の場合はコードブロックを利用してサンプルコードを出力する。
- 出力はMarkdownとする。
- 各種コンテンツはできる限り詳細に記載する。
- コンテンツの中盤ではブレイクタイムとして{inputtext}にまつわるトリビアや豆知識を織り交ぜる。
- 画像や絵文字、アイコン等を使用し視覚的に興味を引く工夫を行う。
- 画像はUnsplashより取得するか、SVG形式で生成する。
- 各種情報には出典を明記する。
- セクションごとに理解度を確認する簡単なクイズを作成する。
- 生成物以外は出力しない（例えば生成物に対するコメントや説明など）
- 指示の最後に「続きを出力」と送られた場合は、指示の続きから出力する。
- 最後まで出力が完了している場合は「続きを出力」と指示された場合でも「出力完了」と返す。
{gen_length}
    """

        if len(st.session_state["alltext"]) > 10:
            del st.session_state["alltext"][0:1]

        if inputtext:
            st.session_state["alltext"].append(inputtext)
            result_text = ""

            with st.spinner(text="生成中..."):
                new_place = st.empty()
                is_init = True
                while True:
                    if is_init:
                        message = "\n".join(st.session_state["alltext"])
                    else:
                        message = "\n".join(st.session_state["alltext"]) + "\n続きを出力"

                    end_search = [
                        value
                        for value in st.session_state["alltext"]
                        if "出力完了" in value
                    ]
                    if len(end_search) != 0:
                        break
                    else:
                        for talk in chat(
                            text=message,
                            settings=instructions,
                            max_tokens=50,
                            model=model,
                        ):
                            result_text += talk
                            new_place.text(result_text)
                        st.session_state["alltext"].append(result_text)

                        graphtext = get_graph_text(result_text)
                        umltext, make = get_uml_text(result_text)

                        if graphtext:
                            st.graphviz_chart(graphtext)

                        if make:
                            st.image(umltext[0])

                        is_init = False

            status_plasce.write("生成完了！")


st.set_page_config(page_title="LearnMateAI", page_icon="📚", layout="wide")

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

openai.api_key = st.secrets["OPEN_AI_KEY"]
main()
