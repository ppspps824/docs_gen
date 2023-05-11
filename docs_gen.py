import time

import openai
import streamlit as st


def chat(text, settings, max_tokens, model):

    messages = [
        {"role": "system", "content": settings},
        {"role": "user", "content": text},
    ]

    # APIを叩く、streamをTrueに
    while True:
        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )
        return resp


def main():
    if "alltext" not in st.session_state:
        st.session_state["alltext"] = []

    st.write("# 📚LearnMateAI ")
    st.write("---")
    status_place = st.empty()

    with st.sidebar:
        with st.form("settings"):
            model = st.selectbox("モデルを選択", ["gpt-4", "gpt-3.5-turbo"])
            inputtext = st.text_input("テーマを入力")
            input_gen_length = st.number_input(
                "生成文字数を入力", min_value=0, step=100, help="0に設定すると指定なしとなります。"
            )
            submit = st.form_submit_button("生成開始")

    if submit:
        if input_gen_length < 300:
            gen_rule = f"初学者が概要を把握できるレベルの資料を{input_gen_length}文字以内で作成してください"
        else:
            gen_rule = (
                f"初学者～中級者が実務で通用するレベルで知識をつけられる研修資料を{input_gen_length}文字以内で作成してください"
            )

        instructions = f"""
あなたは{inputtext}におけるベテランの研修講師です。
{inputtext}について、{gen_rule}。
作成に当たっては以下に厳密に従ってください。
- 指示の最後に[指示：続きを出力]と送られた場合は、[指示：続きを出力]の前の文章の続きを出力する。
    - 例) 
        指示：りんごは赤く甘い、一般 [指示：続きを出力]
        出力：的な家庭でよく食べられている果物です。
        指示：りんごは赤く甘い、一般的な家庭でよく食べられている果物です。 [指示：続きを出力]
        出力：「ふじ」や「紅玉」といった品種が有名です。

- step by stepで複数回検討を行い、その中で一番優れていると思う結果を出力する。
- サンプルではなくそのまま利用できる体裁とする。
- プログラミングやシェルなどコードを入力する内容の場合はコードブロックを利用してサンプルコードを出力する。
- 出力はMarkdownとする。
- 各種コンテンツはできる限り詳細に記載する。
- コンテンツの中盤ではブレイクタイムとして{inputtext}にまつわる豆知識を織り交ぜる。
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
                st.write(f"## テーマ：{inputtext}")
                new_place = st.empty()
                finish_reason = ""
                while True:
                    if finish_reason == "stop":
                        break
                    elif finish_reason == "length":
                        message = "".join(st.session_state["alltext"]) + "[指示：続きを出力]"
                    else:
                        st.error(
                            f"エラーが発生しました。finish_reason={finish_reason}\n{completion}"
                        )
                        st.stop

                    completion = chat(
                        text=message,
                        settings=instructions,
                        max_tokens=3500,
                        model=model,
                    )
                    for chunk in completion:
                        stop_reason = chunk["choices"][0].get("finish_reason", "")
                        next = chunk["choices"][0]["delta"].get("content", "")
                        text += next
                        text = text.replace("[指示：続きを出力]", "")
                        new_place.text(text)

                    st.session_state["alltext"].append(text)

            status_place.write("### 🎉生成完了！\n---")


if __name__ == "__main__":
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
