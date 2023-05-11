import datetime

import openai
import streamlit as st


def chat(text, settings, max_tokens, model):

    messages = [
        {"role": "system", "content": settings},
        {"role": "user", "content": text},
    ]

    try:
        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )
        return resp
    except Exception as e:
        st.error(f"エラー:{e}")
        st.stop()


def main():
    if "alltext" not in st.session_state:
        st.session_state["alltext"] = []

    st.write("# 📚LearnMateAI ")
    st.write("---")
    status_place = st.container()

    with st.sidebar:
        with st.form("settings"):
            model = st.selectbox("モデルを選択", ["gpt-3.5-turbo", "gpt-4"])
            inputtext = st.text_input("テーマを入力")
            level = st.selectbox("レベルを選択", ["初心者", "中級者", "上級者"])
            input_gen_length = st.number_input(
                "生成文字数を入力", min_value=0, step=100, value=1000, help="0に設定すると指定なしとなります。"
            )
            submit = st.form_submit_button("生成開始")
        with st.expander("📚LearnMateAIとは"):
            st.write(
                """
指定されたテーマと対象者のレベルに沿った資料をMarkdown形式で生成するAIです。  
自己学習用の資料作成から、研修資料作成まで幅広く対応します。  

生成文字数を300文字以内に指定すると概要説明資料を生成し、それ以上あるいは0（指定なし）とすると研修に使用できる資料※を生成します。
※理解度を確認するためのクイズ付き

事前に用意した資料をもとにガイドを作成するなどの機能も追加予定です。（社内資料等をもとに新規参入者の受入資料作成や独自マニュアルの作成などに活用できます。）

"""
            )

    if submit:
        if input_gen_length <= 300:
            gen_rule = f"初学者が概要を把握できるレベルの資料を{input_gen_length}文字以内で作成してください"
        else:
            gen_rule = f"{level}が能力を高められる研修資料を{input_gen_length}文字以内で作成してください"

        instructions = f"""
あなたは{inputtext}におけるベテランの研修講師です。
{inputtext}について、{gen_rule}。
作成に当たっては以下に厳密に従ってください。
- 指示の最後に[指示：続きを出力]と送られた場合は、[指示：続きを出力]の前の文章の続きを出力する。
- step by stepで複数回検討を行い、その中で一番優れていると思う結果を出力する。
- サンプルではなくそのまま利用できる体裁とする。
- プログラミングやシェルなどコードを入力する内容の場合はコードブロックを利用してサンプルコードを出力する。
- 出力はMarkdownとする。必要に応じてsummary,detailsなとのHTML要素も組み合わせる。
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
                finish_reason = "init"
                completion = ""
                while True:
                    if finish_reason == "init":
                        message = "".join(st.session_state["alltext"])
                    elif finish_reason == "stop":
                        break
                    elif finish_reason == "length":
                        message = "".join(st.session_state["alltext"]) + "[指示：続きを出力]"
                    else:
                        st.error(f"エラーが発生しました。finish_reason={finish_reason}")
                        st.stop

                    message = message[0:3500]

                    completion = chat(
                        text=message,
                        settings=instructions,
                        max_tokens=3500,
                        model=model,
                    )
                    for chunk in completion:
                        finish_reason = chunk["choices"][0].get("finish_reason", "")
                        next = chunk["choices"][0]["delta"].get("content", "")
                        text += next
                        text = text.replace("[指示：続きを出力]", "")
                        new_place.write(text)

                    st.session_state["alltext"].append(text)

            t_delta = datetime.timedelta(hours=9)
            JST = datetime.timezone(t_delta, "JST")
            now = datetime.datetime.now(JST)

            with status_place:
                st.write("### 🎉生成完了！\n---")
                st.download_button(
                    "テキストをダウンロード",
                    file_name=f"LearnMateAI_{now.strftime('%Y%m%d%H%M%S')}.md",
                    data="\n".join(st.session_state["alltext"]),
                    mime="text/plain",
                )
            st.session_state["alltext"] = []


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
