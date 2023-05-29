import datetime
import io
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import faiss
import openai
import python_minifier
import requests
import streamlit as st
from langchain import PromptTemplate
from langchain.agents import AgentType, initialize_agent, load_tools
from langchain.callbacks.base import BaseCallbackManager
from langchain.callbacks.streamlit import StreamlitCallbackHandler
from langchain.chains import QAGenerationChain
from langchain.chains.summarize import load_summarize_chain
from langchain.chat_models import ChatOpenAI
from langchain.docstore.document import Document
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
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


def chunk_splitter(text):
    # チャンクに分割
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", "。", "、", " ", ""],
        chunk_size=500,  # チャンクの最大トークン数
        chunk_overlap=20,  # チャンクオーバーラップのトークン数
    )
    texts = text_splitter.split_text(text)
    return texts


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
        elif ".csv" in check_name:
            PandasCSVReader = download_loader("PandasCSVReader")
            loader = PandasCSVReader()
            documents = loader.load_data(file=data)
        elif "youtu" in check_name:
            YoutubeTranscriptReader = download_loader("YoutubeTranscriptReader")
            loader = YoutubeTranscriptReader()
            documents = loader.load_data(ytlinks=[name])
        elif "http" in check_name:
            BeautifulSoupWebReader = download_loader("BeautifulSoupWebReader")
            loader = BeautifulSoupWebReader()
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

    return query_engine, documents


def chat(text, settings, model):
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
    error_mes = ""
    for try_time in range(try_count):
        try:
            resp = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                stream=True,
                timeout=120,
                request_timeout=120,
            )
            return resp

        except openai.error.APIError as e:
            print(e)
            print(f"retry:{try_time+1}/{try_count}")
            error_mes = e
            time.sleep(1)
        except openai.error.InvalidRequestError as e:
            print(e)
            print(f"retry:{try_time+1}/{try_count}")
            error_mes = e
            pass
        except (
            openai.error.RateLimitError,
            openai.error.openai.error.APIConnectionError,
        ) as e:
            print(e)
            print(f"retry:{try_time+1}/{try_count}")
            error_mes = e
            time.sleep(10)

    st.error(error_mes)
    st.stop()


def disable():
    st.session_state.disabled = True


def create_messages(
    input_gen_length,
    inputtext,
    supplement,
    select_preset,
    orginal_file,
    preset_file,
):
    if select_preset == "質問":
        instructions = f"""
ルール:Markdownで出力。日本語で出力。データの可視化にはplotlyを用いる。UMLを表現する際はmermaid.js形式で出力する。 {supplement} \n{preset_file["action"][select_preset]["prompt"]}
"""
    else:
        prompt = (
            preset_file["action"][select_preset]["prompt"]
            if orginal_file
            else preset_file["genre"][select_preset]["prompt"]
        )
        instructions = f"""
あなたは{inputtext}の専門家です。
作成に当たっては以下に厳密に従ってください。
- 回答は日本語で行う。
- 文字数は{input_gen_length}とする。
- 指示の最後に続きを出力と送られた場合は、続きを出力の前の文章の続きを出力する。
- step by stepで複数回検討を行い、その中で一番優れていると思う結果を出力する。
- 出力はMarkdownとする。
- UMLを表現する際はmermaid.js形式で出力する。
- データの可視化にはplotlyを用いる。
- 生成物以外は出力しない（例えば生成物に対するコメントや説明など）
{supplement}
{prompt}
            """
    return instructions


def main():
    if "alltext" not in st.session_state:
        st.session_state.alltext = []
        st.session_state.savetext = []
        st.session_state.disabled = False

    input_gen_length = 0
    inputtext = ""
    supplement = ""
    select_preset = ""
    orginal_file = None
    preset_file = None

    # 独自データのうち、プログラムコードを読み込むもの
    cord_reading = ["コード説明", "コードレビュー・リファクタリング", "テスト生成"]

    with open("preset.json", encoding="utf-8") as f1:
        preset_file = json.loads(f1.read())

    all_genre = "\n".join(
        [
            f"| {key} | {value['description']}|"
            for key, value in preset_file["genre"].items()
        ]
    )
    all_action = "\n".join(
        [
            f"| {key} | {value['description']}|"
            for key, value in preset_file["action"].items()
        ]
    )

    col1, col2, _ = st.columns(3)
    with col2:
        st.markdown("#")
        st.markdown("# LearnMate.AI ")
    with col1:
        lottie_url = "https://assets9.lottiefiles.com/packages/lf20_glpbhbuh.json"
        lottie_json = load_lottieurl(lottie_url)
        st_lottie(lottie_json, height=150, loop=False)

    message_place = st.empty()

    with st.sidebar:
        model = st.selectbox("モデルを選択", ["gpt-3.5-turbo", "gpt-4"])
        tab1, tab2 = st.tabs(["ドキュメント生成", "独自データ"])
        with tab1:
            with st.form("tab1"):
                inputtext = st.text_input("テーマ", help="生成したいドキュメントのテーマを記入。必須項目。")
                supplement1 = st.text_area(
                    "入力", help="取り込んで欲しい内容、取り込んで欲しくない内容、その他指示を記入"
                )
                select_preset1 = st.selectbox("ジャンル", preset_file["genre"].keys())
                input_gen_length = st.number_input(
                    "生成文字数を入力",
                    min_value=0,
                    step=100,
                    value=3000,
                    help="0に設定すると指定なしとなります。",
                )

                reading = True

                submit1 = st.form_submit_button(
                    "生成開始",  # on_click=disable, disabled=st.session_state.disabled
                )

        with tab2:
            with st.form("tab2"):
                select_preset2 = st.selectbox("アクション", preset_file["action"].keys())
                supplement2 = st.text_area("入力", help="任意")
                select_file = st.file_uploader("ファイル")
                youtube_url = st.text_input(
                    "URL (WebSite,Youtube...)", help="Youtubeは字幕付動画のみ。"
                )

                orginal_file = select_file if select_file else youtube_url

                reading = True

                submit2 = st.form_submit_button(
                    "生成開始",  # on_click=disable, disabled=st.session_state.disabled
                )

    with st.expander("📚LearnMate.AIとは"):
        st.markdown(
            f"""
#### ・指定されたテーマについて、選択した形式の資料を生成するAIです。  

1. ドキュメント生成 :特定のテーマについてまとめた資料を生成する
2. 独自データ :独自のデータに対して質問、要約、レビュー、リファクタリングなどを行う

#### ・ドキュメント生成ジャンル一覧

|ジャンル|説明|
|---|---|
{all_genre}

#### ・独自データに対するアクション一覧

|アクション|説明|
|---|---|
{all_action}

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

    for no, info in enumerate(st.session_state.savetext):
        t_delta = datetime.timedelta(hours=9)
        JST = datetime.timezone(t_delta, "JST")
        now = datetime.datetime.now(JST)
        with st.expander(f'{info["theme"]} : {info["origine_name"]}'):
            if info["origine_name"]:
                data = f"## {info['theme']} : {info['origine_name']}\n入力 : {info['supplement']}\n---\n{info['value']}"
            else:
                data = info["theme"] + "\n" + info["value"]
            marp = """
---
marp: true
theme: normal
paginate: true
class: invert
---
<!--
headingDivider: 2
-->

            """
            st.download_button(
                "テキストをダウンロード",
                file_name=f"{info['theme']}_{now.strftime('%Y%m%d%H%M%S')}.md",
                data=marp + data if select_preset == "プレゼンテーションスライド作成" else data,
                mime="text/plain",
                key=f"old_text{no}",
            )
            if info["origine_name"]:
                st.markdown(f"## {info['theme']} : {info['origine_name']}")
                st.markdown(f"入力 : {info['supplement']}")
                st.markdown("---")
                st.markdown(f"{info['value']}")

            else:
                st.markdown(f"## {info['theme']}")
                st.markdown(info["value"])

    if any([submit1, submit2]):
        st.session_state.alltext = []
        if submit1:
            supplement = supplement1
            select_preset = select_preset1
            orginal_file = ""
            if not inputtext:
                message_place.error("テーマを入力してください", icon="🥺")
                st.stop()

        if submit2:
            supplement = supplement2
            select_preset = select_preset2
            inputtext = select_preset2

        instructions = create_messages(
            input_gen_length,
            inputtext,
            supplement,
            select_preset,
            orginal_file,
            preset_file,
        )

        st.markdown("---")
        if orginal_file:
            if type(orginal_file) == str:
                st.markdown(f"## {inputtext} : {orginal_file}")
            else:
                st.markdown(f"## {inputtext} : {orginal_file.name}")
        else:
            st.markdown(f"## {inputtext}")

        status_place = st.container()
        lottie_url = "https://assets4.lottiefiles.com/packages/lf20_45movo.json"
        spinner_lottie_json = load_lottieurl(lottie_url)
        with st_lottie_spinner(spinner_lottie_json, height=200):
            st.markdown("---")
            llm = ChatOpenAI(
                temperature=0,
                model_name=model,
                streaming=True,
                max_tokens=2000,
                callback_manager=BaseCallbackManager(
                    [WrapStreamlitCallbackHandler()],
                ),
            )

            if all(
                [
                    orginal_file,
                    select_preset not in cord_reading,
                ]
            ):
                if type(orginal_file) == str:
                    query_engine, documents = make_query_engine(
                        orginal_file,
                        llm=llm,
                        reading=False,
                        name=orginal_file,
                    )
                    file_text = documents[0].text
                else:
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        fp = Path(tmp_file.name)
                        fp.write_bytes(orginal_file.getvalue())
                        query_engine, documents = make_query_engine(
                            fp,
                            llm=llm,
                            reading=False,
                            name=orginal_file.name,
                        )
                        file_text = documents[0].text
            if select_preset in cord_reading:
                file_text = (
                    preset_file["action"][select_preset]["prompt"]
                    + "\n------------\n"
                    + python_minifier.minify(
                        io.StringIO(orginal_file.getvalue().decode("utf-8")).read()
                    )
                )

            text = ""

            if all(
                [
                    orginal_file,
                    select_preset == "Q&A生成",
                ]
            ):
                # QAの生成
                templ1 = """You are a smart assistant designed to help high school teachers come up with reading comprehension questions.
                Given a piece of text, you must come up with a question and answer pair that can be used to test a student's reading comprehension abilities.
                When coming up with this question/answer pair, you must respond in the following format:
                ```
                {{
                    "question": "$YOUR_QUESTION_HERE",
                    "answer": "$THE_ANSWER_HERE"
                }}
                ```

                Everything between the ``` must be valid json.
                answer in Japanese.
                """
                templ2 = """Please come up with a question/answer pair, in the specified JSON format, for the following text:
                ----------------
                {text}"""

                # プロンプトテンプレートの準備
                prompt = ChatPromptTemplate.from_messages(
                    [
                        SystemMessagePromptTemplate.from_template(templ1),
                        HumanMessagePromptTemplate.from_template(templ2),
                    ]
                )
                texts = chunk_splitter(file_text)
                chain = QAGenerationChain.from_llm(llm=llm, prompt=prompt)
                for value in texts:
                    st.write(chain.run(value))
                text = "\n".join(texts)

            elif all(
                [
                    orginal_file,
                    select_preset == "質問",
                ]
            ):
                response = query_engine.query(instructions)

            elif all(
                [
                    orginal_file,
                    select_preset == "要約",
                ]
            ):
                prompt_template = f"""Write a concise summary of the following:


{{text}}

{supplement}
CONCISE SUMMARY IN JAPANESE:"""
                PROMPT = PromptTemplate(
                    template=prompt_template, input_variables=["text"]
                )
                texts = chunk_splitter(file_text)
                chain = load_summarize_chain(llm, chain_type="stuff", prompt=PROMPT)
                docs = [Document(page_content=t) for t in texts[:3]]
                text = chain.run(docs)

            else:
                prompt = inputtext + file_text if orginal_file else inputtext
                st.session_state.alltext.append(prompt)
                finish_reason = "init"
                new_place = st.empty()

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

                    if model == "gpt-3.5-turbo":
                        message = message[-2500:]
                    else:
                        message = message[-6500:]

                    completion = chat(
                        text=message,
                        settings=instructions,
                        model=model,
                    )
                    for chunk in completion:
                        finish_reason = chunk["choices"][0].get("finish_reason", "")
                        next = chunk["choices"][0]["delta"].get("content", "")
                        text += next
                        text = text.replace("続きを出力", "")
                        new_place.write(text)

                    st.session_state.alltext.append(text)

            if orginal_file:
                if type(orginal_file) == str:
                    origine_name = orginal_file
                else:
                    origine_name = orginal_file.name
            else:
                origine_name = select_preset

            st.session_state.savetext.append(
                {
                    "theme": inputtext,
                    "value": text if text else response.response,
                    "supplement": supplement,
                    "origine_name": origine_name,
                }
            )

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
                    data=text if text else response.response,
                    mime="text/plain",
                    key="current_text",
                )


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
    # os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
    # os.environ["GOOGLE_CSE_ID"] = st.secrets["GOOGLE_CSE_ID"]

    main()
