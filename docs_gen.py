import openai
import pandoc
import requests
import streamlit as st

st.set_page_config(
    layout="wide",
)

openai.api_key = st.secrets["OPEN_AI_KEY"]
DEEPL_APY_KEY = st.secrets["DEEPL_APY_KEY"]


instructions = """
[Execution Description]
Create a system requirement definition document to realize user requirements.
Based on the information entered, output the document in Markdown format by faithfully following the notes below.

[Notes]
- Act as a professional system engineer.
- Do not output the input information.
- Output in a format that can be used as a document as it is.
- Do not answer questions about content not covered in the instructions.
- Give answers in a step-by-step, logical manner.
- Each item should clearly state the 5W1H.
- If requirements are unclear, make them general.
- Describe in detail at a level that enables system design.
- Figures should be prepared in Graphviz format, and no other comments should be included.
- Do not output the title of the indicated content, but only the text.
- Insert line breaks and spaces as appropriate to ensure correct display in markdown format.
- Responses should be limited to 300 characters.
- {{Answer in Japanese}}
"""
# instructions = """
# [実行内容]
# ユーザーの要望を実現するためのシステム要件定義書を作成します。
# 入力された情報をもとに、以下の注意点に忠実に従ってMarkdown形式で出力してください。

# [注意点]
# プロのシステムエンジニアとしてふるまう。
# 入力された情報は出力しない。
# そのままドキュメントとして使用できる形式で出力する。
# 指示にない範囲の内容について回答しない。
# 段階的、論理的に考えて答えを出す。
# 各項目は5W1Hを明確に記載する。
# 要件が不明確な場合は、一般的な内容にする。
# システム設計が可能なレベルで詳細に記述すること。
# 図はGraphviz形式で作成し、その他のコメントなどは含めない。
# 指示された内容のタイトルは出力せず本文のみを出力する
# markdown形式で正しく表示されるように適宜改行やスペースを挿入する。
# 回答は300字以内とする。
# 日本語で回答する。
# """


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


def transelate(text, source_lang="JA", target_lang="EN"):
    # パラメータの指定
    params = {
        "auth_key": DEEPL_APY_KEY,
        "text": text,
        "source_lang": source_lang,  # 翻訳対象の言語
        "target_lang": target_lang,  # 翻訳後の言語
    }

    # リクエストを投げる
    request = requests.post("https://api-free.deepl.com/v2/translate", data=params)
    result = request.json()

    return result


def main():
    st.write("# ドキュメントジェネレーター")

    st.write("要望を入力してください。すべて欄を埋める必要はありません。")
    user_input = [
        {
            "title": "[背景・現状の課題]",
            "value": st.text_area(
                "背景・現状の課題",
                help="システム開発を行うにあたって、現在の課題であったり、システム開発に関わる背景を記入します。",
                value="""現在稼働している販売管理システムは2010年に開発されたものであり、サーバーOSの保守が2024年に切れてしまう。また、機能面でも不足が見えており、これを機に刷新を考えています。""",
            ),
        },
        {
            "title": "[システム化の目的]",
            "value": st.text_area(
                "システム化の目的",
                help="課題や背景を受けて、そのシステム化の目的を記入します。",
                value="""販売管理システムをリニューアルし、現在の業務フローに合わせて最適化します。""",
            ),
        },
        {
            "title": "[ゴール・目標]",
            "value": st.text_area(
                "ゴール・目標",
                help="ゴールは何なのかを記述します。",
                value="""販売管理システムの刷新。
    現在サポートされていない一括納入形式の売買をサポート締め処理の高速化（現在8時間程度かかっているので、1時間程度で終わらせたい）""",
            ),
        },
        {
            "title": "[予算]",
            "value": st.text_area(
                "予算",
                help="プロジェクト全体の予算を記入します。",
                value="""4,000万円（サーバー/OS購入費用含む）。クライアントPCは現状のものを流用予定。""",
            ),
        },
        {
            "title": "[対応期限]",
            "value": st.text_area(
                "対応期限",
                help="システム稼働の期限を記入します。",
                value="""2023年末までに稼働開始（現行システムとの並行運用）。2024年3月までに現行システムを停止。""",
            ),
        },
        {
            "title": "[対象部署]",
            "value": st.text_area(
                "対象部署",
                help="このプロジェクトに関わる部署をリストアップします。",
                value="""業務部""",
            ),
        },
        {
            "title": "[運用体制]",
            "value": st.text_area(
                "運用体制",
                help="システムが稼働した後の運用体制を記述します。",
                value="""[運用]業務部、営業部（入力のみ）[保守メンバー]情報システム部""",
            ),
        },
        {
            "title": "[現状の資産]",
            "value": st.text_area(
                "現状の資産",
                help="ハードウェアやソフトウェアなど、現状自社にある資産をリストアップします。",
                value="""サーバー
    Windows 201X。OS、ハードウェア共に保守が切れるので運用への利用対象外
    クライアント
    Windows 10""",
            ),
        },
        {
            "title": "[提案で必要な範囲]",
            "value": st.text_area(
                "提案で必要な範囲",
                help="システム開発のみ、または運用や保守まで依頼したいのかなどシステム提案の範囲を明確にします。",
                value="""システム開発全般
    運用メンバーへの教育
    移行計画書の作成
    セキュリティレベルでの保守
    サーバーセットアップ手順書""",
            ),
        },
        {
            "title": "[希望納品物]",
            "value": st.text_area(
                "希望納品物",
                help="納品物の形態を記入します。",
                value="""ソースコード一式
    システムがインストールされたサーバー""",
            ),
        },
        {
            "title": "[開発言語や手法]",
            "value": st.text_area(
                "開発言語や手法",
                help="システム稼働の期限を記入します。",
                value="""プログラミング言語はJavaまたはC#
    データベースはSQL Server""",
            ),
        },
        {
            "title": "[機能要求]",
            "value": st.text_area(
                "機能要求",
                help="システムに必要な機能を記入します。機能だけでなくパフォーマンスや非機能要件についても、必要なものは記入します。",
                value="""現行の販売フロー網羅
    締め処理の高速化
    Webブラウザを使ったシステム""",
            ),
        },
        {
            "title": "[テスト要件]",
            "value": st.text_area(
                "テスト要件",
                help="システムのテストに関して要望がある場合には、それを記入します。",
                value="""単体テストから結合テストまでのテスト仕様書およびその結果を提出お願いします。""",
            ),
        },
        {
            "title": "[移行要件]",
            "value": st.text_area(
                "移行要件",
                help="現行のシステムがあり、その移行についても提案が必要な場合に記入します。",
                value="""現行システムにあるデータを新規システムへ移行してください。データ量は約10万件です（販売テーブル）。""",
            ),
        },
        {
            "title": "[運用保守]",
            "value": st.text_area(
                "運用保守",
                help="運用や保守について要望がある場合に記入します。",
                value="""サーバーのセキュリティレベルでの保守をお願いします。サーバー自体の保守はハードウェアベンダーで問題ありません。""",
            ),
        },
        {
            "title": "[教育や研修]",
            "value": st.text_area(
                "教育や研修",
                help="運用メンバーに対する教育など、要望がある場合に記入します。",
                value="""運用メンバー（3人の予定）、営業メンバー（10人の予定）への運用教育をお願いします。""",
            ),
        },
        {
            "title": "[開発体制]",
            "value": st.text_area(
                "開発体制",
                help="開発体制について要望がある場合に記入します。",
                value="""最低4人（プロジェクトマネージャ1名含む）での開発体制をお願いします。外部委託（オフショア含む）を行う場合には、文書にて体制図をお願いします。""",
            ),
        },
        {
            "title": "[補足情報]",
            "value": st.text_area(
                "補足情報", help="業務フローなどの補足情報を記入します。", value="""業務フロー xxx,yyy・・・"""
            ),
        },
    ]

    user_input_text = "\n".join(
        [info["title"] + "\n" + info["value"] for info in user_input if info["value"]]
    )

    submit = st.button("ドキュメントを生成する")

    contents = [
        {
            "title": "システム概要",
            "point": "関係メンバー全員、誰が読んでもわかるように、今回開発するシステムの概要を100字以内で記載。",
            "graph": False,
        },
        {
            "title": "システム構成図",
            "point": "一目でシステムの構成がわかる構成図を記載。データと業務のフローがカバーされていること。",
            "graph": True,
        },
        {
            "title": "プロジェクト体制",
            "point": "",
            "graph": False,
        },
        # {"title": "機能要件 機能", "point": "機能を大区分、中区分、小区分でブレイクダウンする。", "graph": False},
        # {"title": "機能要件 画面", "point": "ユーザーとやり取りを行うために必要な画面定義を記載する。", "graph": False},
        # {"title": "機能要件 情報・データ・ログ", "point": "データ項目、処理方法などを記載。", "graph": False},
        # {
        #     "title": "機能要件 外部インタフェース",
        #     "point": "外部インターフェイスを定義して記載。入力される項目など",
        #     "graph": False,
        # },
        # {
        #     "title": "非機能要件 ユーザビリティ及びアクセシビリティ",
        #     "point": "誰がどう使えればいいのか、定義して記載。",
        #     "graph": False,
        # },
        # {"title": "非機能要件 性能", "point": "性能に関する事項＋閾値を記載。", "graph": False},
        # {"title": "非機能要件 信頼性", "point": "", "graph": False},
        # {"title": "非機能要件 拡張性", "point": "", "graph": False},
        # {"title": "非機能要件 継続性", "point": "", "graph": False},
        # {"title": "情報セキュリティ アクセス制御方法", "point": "", "graph": False},
        # {"title": "情報セキュリティ アクセス認証方法", "point": "", "graph": False},
        # {"title": "情報セキュリティ データの暗号化", "point": "", "graph": False},
        # {"title": "情報セキュリティ ウィルス対策", "point": "", "graph": False},
        # {"title": "情報セキュリティ 侵入・攻撃対策", "point": "", "graph": False},
        # {"title": "情報セキュリティ その他利用制限", "point": "", "graph": False},
        # {"title": "情報セキュリティ 不正接続対策", "point": "", "graph": False},
        # {"title": "情報セキュリティ 外部媒体保存制限（運用ポリシー）", "point": "", "graph": False},
        # {
        #     "title": "稼働環境",
        #     "point": "環境に関して記載。対応しているブラザなど。要されるセキュリティーに応じて最適な環境を記載",
        #     "graph": False,
        # },
        # {"title": "テスト 機能テスト", "point": "", "graph": False},
        # {"title": "テスト ユーザビリティテスト", "point": "", "graph": False},
        # {"title": "テスト 負荷テスト", "point": "", "graph": False},
        # {"title": "テスト セキュリティテスト", "point": "", "graph": False},
        # {"title": "テスト 担保する範囲とテスト範囲の定義", "point": "", "graph": False},
        # {"title": "テスト テスト環境", "point": "どのような環境でだれが行うのか", "graph": False},
        # {"title": "テスト 完了基準", "point": "", "graph": False},
        # {"title": "テスト 使用するツール", "point": "", "graph": False},
        # {"title": "テスト テストデータ", "point": "どのようなデータか、どのように用意するのか", "graph": False},
        # {"title": "移行要件 移行のプロセス、タイミング", "point": "", "graph": False},
        # {"title": "運用要件 教育", "point": "運用・利用・活用方法の教育について", "graph": False},
        # {"title": "運用要件 運用", "point": "運用体制、運用業務", "graph": False},
        # {"title": "運用要件 保守", "point": "", "graph": False},
        # {"title": "予算", "point": "各工程で必要となる費用を算出して記載", "graph": False},
        # {"title": "スケジュール", "point": "表形式で作成", "graph": False},
    ]

    contents_text = [
        f'以下の要望を実現するために、要件定義書に記載する{content["title"]}部分のみを日本語で作成してください。\n[注意点]\n{content["point"]}'
        for content in contents
    ]

    if submit:
        submit = False

        transe_input = transelate(user_input_text, "JA", "EN")

        all_text = ""
        for value, content_info in zip(contents_text, contents):
            transe_value = value
            text_place = st.empty()
            graph_place = st.empty()
            result_text = ""
            title = "##  " + content_info["title"] + "\n\n"
            for talk in chat(
                f"{transe_value}/n/n{transe_input}",
                settings=instructions,
            ):
                result_text += talk
                if content_info["graph"]:
                    text_place.write(title + result_text)
                    graph_place.graphviz_chart(result_text)
                else:
                    text_place.write(title + result_text)

            all_text += result_text

        doc = pandoc.read(all_text)
        docfile = pandoc.write(doc, format="docx")

        st.download_button(
            "Word形式でダウンロード",
            data=docfile,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


main()
