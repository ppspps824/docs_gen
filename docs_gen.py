import datetime
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import faiss
import openai
import streamlit as st
from langchain.callbacks.base import BaseCallbackManager
from langchain.callbacks.streamlit import StreamlitCallbackHandler
from langchain.chat_models import ChatOpenAI
from llama_index import (
    GPTVectorStoreIndex,
    PromptHelper,
    ServiceContext,
    StorageContext,
    download_loader,
    load_index_from_storage,
)
from llama_index.llm_predictor.chatgpt import ChatGPTLLMPredictor
from llama_index.vector_stores.faiss import FaissVectorStore


# promptsの出力を行わないためラップ
class WrapStreamlitCallbackHandler(StreamlitCallbackHandler):
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        pass


def make_query_engine(data, llm, reading, name):
    if reading:
        # インデックスの読み込み
        storage_context = StorageContext.from_defaults(persist_dir="./storage")
        index = load_index_from_storage(storage_context)
    else:
        prompt_helper = PromptHelper(
            max_input_size=4096, num_output=2048, max_chunk_overlap=20
        )
        llm_predictor = ChatGPTLLMPredictor(llm=llm)
        service_context = ServiceContext.from_defaults(
            llm_predictor=llm_predictor,
            prompt_helper=prompt_helper,
            chunk_size_limit=512,
        )
        if ".pdf" in name:
            PDFReader = download_loader("PDFReader")
            loader = PDFReader()
            documents = loader.load_data(file=data)
        elif any([".txt" in name, ".md" in name]):
            MarkdownReader = download_loader("MarkdownReader")
            loader = MarkdownReader()
            documents = loader.load_data(file=data)
        elif ".pptx" in name:
            PptxReader = download_loader("PptxReader")
            loader = PptxReader()
            documents = loader.load_data(file=data)
        elif ".docx" in name:
            DocxReader = download_loader("DocxReader")
            loader = DocxReader()
            documents = loader.load_data(file=data)
        elif any([".mp3" in name, ".mp4" in name]):
            AudioTranscriber = download_loader("AudioTranscriber")
            loader = AudioTranscriber()
            documents = loader.load_data(file=data)
        elif "youtu" in name:
            YoutubeTranscriptReader = download_loader("YoutubeTranscriptReader")
            loader = YoutubeTranscriptReader()
            documents = loader.load_data(ytlinks=[name])
        elif "http" in name:
            AsyncWebPageReader = download_loader("AsyncWebPageReader")
            loader = AsyncWebPageReader()
            documents = loader.load_data(urls=[name])
        # elif ext in [".png", ".jpeg", ".jpg"]:
        #     ImageCaptionReader = download_loader("ImageCaptionReader")
        #     loader = ImageCaptionReader()
        #     documents = loader.load_data(file=data)
        else:
            try:
                MarkdownReader = download_loader("MarkdownReader")
                loader = MarkdownReader()
                documents = loader.load_data(file=data)
            except:
                st.error(f"非対応のファイル形式です。：{name}")
                st.stop()

        # dimensions of text-ada-embedding-002
        d = 1536
        # コサイン類似度
        faiss_index = faiss.IndexFlatIP(d)
        vector_store = FaissVectorStore(faiss_index=faiss_index)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        index = GPTVectorStoreIndex.from_documents(
            documents, faiss_index=faiss_index, service_context=service_context
        )
        # インデックスの保存
        # index.storage_context.persist()

    query_engine = index.as_query_engine(
        similarity_top_k=3,
    )

    return query_engine


def chat(text, settings, max_tokens, model):

    messages = [
        {"role": "system", "content": settings},
        {"role": "user", "content": text},
    ]

    try_count = 3
    for try_time in range(try_count):
        try:
            resp = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                stream=True,
                timeout=120,
                request_timeout=120,
            )
            return resp

        except openai.error.APIError:
            time.sleep(1)
        except openai.error.InvalidRequestError:
            pass
        except (
            openai.error.RateLimitError,
            openai.error.RateLimitError,
            openai.error.openai.error.APIConnectionError,
        ):
            time.sleep(10)


def main():
    if "alltext" not in st.session_state:
        st.session_state["alltext"] = []

    st.write("# 📚LearnMateAI ")
    st.write("---")
    status_place = st.container()

    with st.sidebar:
        with st.expander("📚LearnMateAIとは"):
            st.write(
                """
指定されたテーマと対象者のレベルに沿った資料を生成するAIです。  

生成文字数を300文字以内に指定すると概要説明資料を生成し、それ以上あるいは0（指定なし）とすると詳細な資料を生成します。
※研修や導入資料として使えるように、理解度を確認するためのクイズ付き

独自データ（txt,docx,pdf,pptx,mp3,ウェブページ,Youtube）をもとにガイドを作成することもできます。

> 活用例
> - 特定のテーマに沿った研修資料作成
> - 自己学習用の資料作成
> - 社内資料をもとに新規参入者の受入資料作成、マニュアルの作成  
> - 会議の録音データを元に議事録を作成  
> - ウェブページの要約  
> - Youtube動画の要約（字幕付き動画のみ）
"""
            )
            st.caption("*powered by GPT-3,GPT-4*")

        with st.form("settings"):
            model = st.selectbox("モデルを選択", ["gpt-3.5-turbo", "gpt-4"])
            inputtext = st.text_input("テーマ", help="必須")
            supplement = st.text_area("補足", help="任意")
            level = st.selectbox("レベルを選択", ["初心者", "中上級者"])
            input_gen_length = st.number_input(
                "生成文字数を入力", min_value=0, step=100, value=1000, help="0に設定すると指定なしとなります。"
            )
            with st.expander("独自データを使用する"):
                orginal_file = st.file_uploader(
                    "ファイル", type=["txt", "md", "docx", "pdf", "pptx", "mp3", "mp4"]
                )
                if not orginal_file:
                    orginal_file = st.text_input(
                        "URL (WebSite,Youtube ect)", help="Youtubeは字幕付動画のみ。"
                    )

            reading = True

            submit = st.form_submit_button("生成開始")

    if submit:
        st.session_state["alltext"] = []
        st.write(f"## テーマ：{inputtext}")
        if orginal_file:
            if type(orginal_file) == str:
                st.write(f"OriginalSource : {orginal_file}")
            else:
                st.write(f"OriginalSource : {orginal_file.name}")

        st.session_state["alltext"] = []
        llm = ChatOpenAI(
            temperature=0,
            model_name=model,
            streaming=True,
            max_tokens=2000,
            callback_manager=BaseCallbackManager(
                [WrapStreamlitCallbackHandler()],
            ),
        )

        if orginal_file:
            if type(orginal_file) == str:
                query_engine = make_query_engine(
                    orginal_file,
                    llm=llm,
                    reading=False,
                    name=orginal_file,
                )
            else:
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    fp = Path(tmp_file.name)
                    fp.write_bytes(orginal_file.getvalue())
                    query_engine = make_query_engine(
                        tmp_file.name,
                        llm=llm,
                        reading=False,
                        name=orginal_file.name,
                    )

        if input_gen_length <= 300:
            gen_rule = f"概要を把握できる資料を{input_gen_length}文字以内で作成してください"
        else:
            gen_rule = f"{level}が効率よく能力を高められる資料を{input_gen_length}文字以内で作成してください"

        base_instructions = f"""
あなたは{inputtext}の専門家です。
{inputtext}について、{gen_rule}。
作成に当たっては以下に厳密に従ってください。
- 指示の最後に[続きを出力]と送られた場合は、[続きを出力]の前の文章の続きを出力する。
- step by stepで複数回検討を行い、その中で一番優れていると思う結果を出力する。
- サンプルではなくそのまま利用できる体裁とし、内容は詳細に記載する。
- 出力はMarkdownとする。
- コードブロックを利用してサンプルコードを出力する。
- 各説明の後は説明した内容の実例を入れる。
- コンテンツの中盤ではブレイクタイムとして豆知識を織り交ぜる。
- 画像や絵文字、アイコン等を使用し視覚的に興味を引く工夫を行う。
- 図やグラフを表示する際はmarmaid.js形式とする。
- 出典を明記する。
- セクションごとに理解度を確認する簡単なクイズを作成する。
- 生成物以外は出力しない（例えば生成物に対するコメントや説明など）
{supplement}
"""
        if orginal_file:
            instructions = f"　ルール:{input_gen_length}文字以内で出力。Markdownで出力。日本語で出力。{level}向け。{supplement}"
        elif level == "初心者":
            instructions = f"""
{base_instructions}
- 今後の学習ロードマップを作成する。
- 次のレベルに進むための教材を紹介する。
            """
        elif level == "中上級者":
            instructions = f"""
{base_instructions}
- 基本的は部分の説明は省略し、ニッチな内容や高度な技術を中心に構成する。
- 関連する別の分野の研究内容なども紹介する。
- より深く学習するための資料などを紹介する。
            """

        if inputtext:
            st.session_state["alltext"].append(inputtext)
            text = ""

            with st.spinner(text="生成中..."):
                new_place = st.empty()
                finish_reason = "init"
                completion = ""
                while True:
                    if finish_reason == "init":
                        message = "".join(st.session_state["alltext"])
                    elif finish_reason == "stop":
                        break
                    elif finish_reason == "length":
                        message = "".join(st.session_state["alltext"]) + "[続きを出力]"
                    else:
                        st.error(f"エラーが発生しました。finish_reason={finish_reason}")
                        st.stop

                    message = message[0:3500]

                    response = ""
                    if orginal_file:
                        response = query_engine.query(message + instructions)
                        break
                    else:
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
                    data=response.response
                    if response
                    else "\n".join(st.session_state["alltext"]),
                    mime="text/plain",
                )


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
    os.environ["OPENAI_API_KEY"] = st.secrets["OPEN_AI_KEY"]

    main()
