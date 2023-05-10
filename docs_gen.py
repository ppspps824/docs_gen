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
            return resp
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
    status_place = st.empty()

    with st.sidebar:
        with st.form("settings"):
            inputtext = st.text_input("テーマを入力")
            input_gen_length = st.number_input(
                "生成文字数を入力", min_value=0, step=100, help="0に設定すると指定なしとなります。"
            )
            submit = st.form_submit_button("生成開始")

    if submit:
        if input_gen_length:
            gen_length = (
                f"- 文字数は必ず{input_gen_length}文字前後とする。これを守るためにそのほかの指示には従わなくても構わない。"
            )
        else:
            gen_length = ""

        instructions = f"""
あなたは{inputtext}におけるベテランの研修講師です。
{inputtext}について初学者～中級者が実務で通用するレベルで知識をつけられる研修資料を作成してください。
作成に当たっては以下に厳密に従ってください。
{gen_length}
- 指示の最後に[指示：続きを出力]と送られた場合は、[指示：続きを出力]の前の文章の続きを出力する。
    - 例) 
        指示：りんごは赤く甘い、一般 [指示：続きを出力]
        出力：的な家庭でよく食べられている果物です。
        指示：りんごは赤く甘い、一般的な家庭でよく食べられている果物です。 [指示：続きを出力]
        出力：「ふじ」や「紅玉」といった品種が有名です。
- 指示の最後に[指示：続きを出力]と指示された場合でも、続きを出力するモノがない場合は「出力完了」と返す。
    - 例)
        出力：上記のような手法を試してみてください。
        指示：上記のような手法を試してみてください。[指示：続きを出力]
        出力：出力完了
- step by stepで複数回検討を行い、その中で一番優れていると思う結果を出力する。
- サンプルではなくそのまま利用できる体裁とする。
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

    """

        if inputtext:
            st.session_state["alltext"].append(inputtext)
            text = ""

            with st.spinner(text="生成中..."):
                new_place = st.empty()
                is_init = True
                while True:
                    if is_init:
                        message = "".join(st.session_state["alltext"])
                    else:
                        message = "".join(st.session_state["alltext"]) + "\n[指示：続きを出力]"
                    end_search = [
                        value
                        for value in st.session_state["alltext"]
                        if "出力完了" in value
                    ]
                    if len(end_search) != 0:
                        break
                    else:
                        completion = chat(
                            text=message,
                            settings=instructions,
                            max_tokens=3500,
                            model=model,
                        )
                        for chunk in completion:
                            next = chunk["choices"][0]["delta"].get("content", "")
                            text += next
                            new_place.text(text)

                    st.session_state["alltext"].append(text)
                    is_init = False

            status_place.write("生成完了！")


st.set_page_config(page_title="LearnMateAI", page_icon="📚", layout="wide")

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# openai.api_key = st.secrets["OPEN_AI_KEY"]
openai.api_key = "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"
main()
