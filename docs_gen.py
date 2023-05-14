import datetime
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import faiss
import openai
import requests
import streamlit as st
from langchain.agents import AgentType, initialize_agent, load_tools
from langchain.callbacks.base import BaseCallbackManager
from langchain.callbacks.streamlit import StreamlitCallbackHandler
from langchain.chat_models import ChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
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
from streamlit_lottie import st_lottie, st_lottie_spinner


# promptsの出力を行わないためラップ
class WrapStreamlitCallbackHandler(StreamlitCallbackHandler):
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        pass


def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()


def make_query_engine(data, llm, reading, name):

    check_name = name.lower()
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
        if ".pdf" in check_name:
            PDFReader = download_loader("PDFReader")
            loader = PDFReader()
            documents = loader.load_data(file=data)
        elif any([".txt" in check_name, ".md" in name]):
            MarkdownReader = download_loader("MarkdownReader")
            loader = MarkdownReader()
            documents = loader.load_data(file=data)
        elif ".pptx" in check_name:
            PptxReader = download_loader("PptxReader")
            loader = PptxReader()
            documents = loader.load_data(file=data)
        elif ".docx" in check_name:
            DocxReader = download_loader("DocxReader")
            loader = DocxReader()
            documents = loader.load_data(file=data)
        elif any([".mp3" in check_name, ".mp4" in check_name]):
            AudioTranscriber = download_loader("AudioTranscriber")
            loader = AudioTranscriber()
            documents = loader.load_data(file=data)
        elif "youtu" in check_name:
            YoutubeTranscriptReader = download_loader("YoutubeTranscriptReader")
            loader = YoutubeTranscriptReader()
            documents = loader.load_data(ytlinks=[name])
        elif "http" in check_name:
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
    # # 使用するツールをロード
    # tools = ["google-search", "python_repl"]
    # tools = load_tools(tools, llm=model)

    # system_template = settings
    # human_template = "質問者：{question}"
    # system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)
    # human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)

    # chat_prompt = ChatPromptTemplate.from_messages(
    #     [system_message_prompt, human_message_prompt]
    # )
    # prompt_message_list = chat_prompt.format_prompt(
    #     language="日本語", question=text
    # ).to_messages()
    # print(prompt_message_list)
    # try:
    #     agent = initialize_agent(
    #         tools=tools,
    #         llm=model,
    #         agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    #         verbose=True,
    #     )
    #     response = agent.run(prompt_message_list)

    # except Exception as e:
    #     response = str(e)
    #     if not response.startswith("Could not parse LLM output: `"):
    #         raise e
    #     response = response.removeprefix("Could not parse LLM output: `").removesuffix(
    #         "`"
    #     )

    # return response
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

        except openai.error.APIError as e:
            print(e)
            print(f"retry:{try_time+1}/{try_count}")
            time.sleep(1)
        except openai.error.InvalidRequestError as e:
            print(e)
            print(f"retry:{try_time+1}/{try_count}")
            pass
        except (
            openai.error.RateLimitError,
            openai.error.openai.error.APIConnectionError,
        ) as e:
            print(e)
            print(f"retry:{try_time+1}/{try_count}")
            time.sleep(10)


def disable():
    st.session_state.disabled = True


def create_messages(
    input_gen_length=0, inputtext="", supplement="", level="", orginal_file=None
):
    if input_gen_length <= 300:
        gen_rule = f"概要を把握できる資料を{input_gen_length}文字以内で作成してください"
    else:
        gen_rule = f"詳細をまとめた資料を{input_gen_length}文字以内で作成してください"

    base_instructions = f"""
あなたは{inputtext}の専門家です。
{inputtext}について、{gen_rule}。
作成に当たっては以下に厳密に従ってください。
- 指示の最後に続きを出力と送られた場合は、続きを出力の前の文章の続きを出力する。
- step by stepで複数回検討を行い、その中で一番優れていると思う結果を出力する。
- 出力はMarkdownとする。
- 生成物以外は出力しない（例えば生成物に対するコメントや説明など）
        {supplement}
        """
    traning_base = """
- サンプルではなくそのまま利用できる体裁とし、内容は詳細に記載する。
- コードブロックを利用してサンプルコードを出力する。
- 各説明の後は説明した内容の実例を入れる。
- コンテンツの中盤ではブレイクタイムとして豆知識を織り交ぜる。
- 画像や絵文字、アイコン等を使用し視覚的に興味を引く工夫を行う。
- 図やグラフを表示する際はmarmaid.js形式とする。
- 出典を明記する。
- セクションごとに理解度を確認する簡単なクイズを作成する。
                """
    if orginal_file:
        instructions = f"　ルール:Markdownで出力。日本語で出力。{supplement}"
    elif level == "入門資料":
        instructions = f"""
{base_instructions}
{traning_base}
- 今後の学習ロードマップを作成する。
- 次のレベルに進むための教材を紹介する。
                    """
    elif level == "中上級者向け資料":
        instructions = f"""
{base_instructions}
{traning_base}
- 基本的は部分の説明は省略し、ニッチな内容や高度な技術を中心に構成する。
- 関連する別の分野の研究内容なども紹介する。
- より深く学習するための資料などを紹介する。
                    """
    elif level == "フリーフォーマット":
        instructions = base_instructions

    return instructions


def main():
    if "alltext" not in st.session_state:
        st.session_state.alltext = []
        st.session_state.savetext = []
        st.session_state.disabled = False
    col1, col2, _ = st.columns(3)
    with col2:
        st.markdown("#")
        st.markdown("#")
        st.markdown("# LearnMate.AI ")
    with col1:
        lottie_url = "https://assets9.lottiefiles.com/packages/lf20_glpbhbuh.json"
        lottie_json = load_lottieurl(lottie_url)
        st_lottie(lottie_json, height=200, loop=False)

    message_place = st.empty()

    with st.sidebar:
        tab1, tab2, tab3 = st.tabs(["About", "資料作成", "対話検索"])
        with tab1:
            st.markdown("## 📚LearnMate.AIとは")
            st.markdown(
                """
    指定されたテーマについて、選択した形式の資料を生成するAIです。  

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
        with tab2:
            with st.form("tab2"):
                model = st.selectbox("モデルを選択", ["gpt-3.5-turbo", "gpt-4"])
                inputtext = st.text_input("テーマ", help="必須")
                supplement = st.text_area("補足", help="任意")
                level = st.selectbox("形式を選択", ["フリーフォーマット", "入門資料", "中上級者向け資料"])
                input_gen_length = st.number_input(
                    "生成文字数を入力",
                    min_value=0,
                    step=100,
                    value=1000,
                    help="0に設定すると指定なしとなります。",
                )

                reading = True

                submit = st.form_submit_button(
                    "生成開始",  # on_click=disable, disabled=st.session_state.disabled
                )

        with tab3:
            with st.form("tab3"):
                model = st.selectbox("モデルを選択", ["gpt-3.5-turbo", "gpt-4"])
                inputtext = st.text_area("入力")
                orginal_file = st.file_uploader(
                    "ファイル", type=["txt", "md", "docx", "pdf", "pptx", "mp3", "mp4"]
                )
                if not orginal_file:
                    orginal_file = st.text_input(
                        "URL (WebSite,Youtube...)", help="Youtubeは字幕付動画のみ。"
                    )

                reading = True

                submit = st.form_submit_button(
                    "生成開始",  # on_click=disable, disabled=st.session_state.disabled
                )

    if not submit:
        # 紹介動画を流す
        pass

    for no, info in enumerate(st.session_state.savetext):
        t_delta = datetime.timedelta(hours=9)
        JST = datetime.timezone(t_delta, "JST")
        now = datetime.datetime.now(JST)
        with st.expander(f'{info["theme"]}'):
            if info["origine_name"]:
                data = (
                    f"## {info['theme']}"
                    + "\n"
                    + f"OriginalSource : {info['origine_name']}"
                    + "\n"
                    + info["value"]
                )
            else:
                data = info["theme"] + "\n" + info["value"]
            st.download_button(
                "テキストをダウンロード",
                file_name=f"{info['theme']}_{now.strftime('%Y%m%d%H%M%S')}.md",
                data=data,
                mime="text/plain",
                key=f"old_text{no}",
            )
            st.markdown(f"## {info['theme']}")
            if info["origine_name"]:
                st.markdown(f"OriginalSource : {info['origine_name']}")
            st.markdown(info["value"])

    if submit:
        instructions = create_messages(
            input_gen_length, inputtext, supplement, level, orginal_file
        )
        if inputtext:
            st.session_state.alltext = []
            st.markdown("---")
            st.markdown(f"## {inputtext}")

            if orginal_file:
                if type(orginal_file) == str:
                    st.markdown(f"OriginalSource : {orginal_file}")
                else:
                    st.markdown(f"OriginalSource : {orginal_file.name}")
            status_place = st.container()
            lottie_url = "https://assets4.lottiefiles.com/packages/lf20_45movo.json"
            spinner_lottie_json = load_lottieurl(lottie_url)
            with st_lottie_spinner(spinner_lottie_json, height=200):
                st.markdown("---")
                st.session_state.alltext = []
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
                                fp,
                                llm=llm,
                                reading=False,
                                name=orginal_file.name,
                            )

                st.session_state.alltext.append(inputtext)
                text = ""

                new_place = st.empty()
                finish_reason = "init"
                completion = ""
                while True:
                    if finish_reason == "init":
                        message = "".join(st.session_state.alltext)
                    elif finish_reason == "stop":
                        break
                    elif finish_reason == "length":
                        message = "".join(st.session_state.alltext) + "続きを出力"
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
                            text = text.replace("続きを出力", "")
                            new_place.write(text)

                    st.session_state.alltext.append(text)
                    origine_name = ""
                    if orginal_file:
                        if type(orginal_file) == str:
                            origine_name = orginal_file
                        else:
                            origine_name = orginal_file.nam

                    st.session_state.savetext.append(
                        {
                            "theme": inputtext,
                            "value": text,
                            "origine_name": origine_name,
                        }
                    )
                    st.session_state.disabled = False

                t_delta = datetime.timedelta(hours=9)
                JST = datetime.timezone(t_delta, "JST")
                now = datetime.datetime.now(JST)

                with status_place:
                    lottie_url = "https://assets2.lottiefiles.com/datafiles/8UjWgBkqvEF5jNoFcXV4sdJ6PXpS6DwF7cK4tzpi/Check Mark Success/Check Mark Success Data.json"
                    lottie_json = load_lottieurl(lottie_url)
                    st_lottie(lottie_json, height=100, loop=False)
                    st.download_button(
                        "テキストをダウンロード",
                        file_name=f"{inputtext}_{now.strftime('%Y%m%d%H%M%S')}.md",
                        data=response.response
                        if response
                        else "\n".join(st.session_state.alltext),
                        mime="text/plain",
                        key="current_text",
                    )
        else:
            message_place.error("テーマを入力してください", icon="🥺")


if __name__ == "__main__":
    st.set_page_config(page_title="LearnMate.AI", page_icon="📚", layout="wide")

    hide_streamlit_style = """
                <style>
               .block-container {
                    padding-top: 2rem;
                }
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                </style>
                """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    os.environ["OPENAI_API_KEY"] = st.secrets["OPEN_AI_KEY"]
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
    os.environ["GOOGLE_CSE_ID"] = st.secrets["GOOGLE_CSE_ID"]

    main()
