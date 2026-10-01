# %% 준비
import getpass
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    RunnableLambda, RunnableParallel, RunnablePassthrough, RunnableSequence,
)
from langchain_openai import ChatOpenAI

load_dotenv()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
NOTICE = {
    "document_id": "notice-014",
    "text": "  사내 문서 도우미에 새 규정을 등록할 때는 담당자의 검토를 받아야 합니다. "
            "승인된 문서만 검색 대상으로 등록하고, 변경된 규정은 기존 문서와 교체합니다.  ",
}
SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "사내 문서 도우미 운영 공지를 한 문장으로 요약하세요. "
               "담당자 검토, 승인 문서 등록, 변경 문서 교체를 빠뜨리지 마세요."),
    ("human", "{clean_text}"),
])
KEYWORD_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "공지에서 검색에 쓸 짧은 핵심어 세 개를 골라 쉼표로 구분하세요. "
               "번호나 설명을 붙이지 마세요."),
    ("human", "{clean_text}"),
])

# %% 구현
def clean_notice(data):
    # TODO 1: 공지 입력을 검사하고 앞뒤 공백을 제거한 문자열을 반환하세요.
    if not isinstance(data, dict):
        raise ValueError("공지 입력은 dict여야 합니다.")

    text = data.get("text")

    if not isinstance(text, str):
        raise ValueError("text는 문자열이어야 합니다.")

    clean_text = text.strip()

    if not clean_text:
        raise ValueError("공지 내용이 비어 있습니다.")

    return clean_text

def build_prepare():
    # TODO 2: clean_text를 추가한 뒤 text_length를 추가하는 두 단계를 반환하세요.
    return (
        RunnablePassthrough()
        .assign(
            clean_text=RunnableLambda(clean_notice)
        )
        .assign(
            text_length=RunnableLambda(
                lambda data: len(data["clean_text"])
            )
        )
    )

def build_chain(model):
    summary_chain = SUMMARY_PROMPT | model | StrOutputParser()
    keyword_chain = KEYWORD_PROMPT | model | StrOutputParser()
    # TODO 3: 두 branch를 병렬로 묶고 원문을 유지하는 전체 순차 체인을 반환하세요.

    return RunnableSequence(
        build_prepare(),
        RunnablePassthrough().assign(
            analysis=RunnableParallel(
                summary=summary_chain,
                keywords=keyword_chain,
            )
        )
    )

# %% 결과 확인
def main():
    # 이 확인은 모델을 호출하지 않습니다. 입력을 실제로 보존했는지 봅니다.
    original = NOTICE.copy()
    assert RunnablePassthrough().invoke(NOTICE) == original
    prepared = build_prepare().invoke(NOTICE)
    assert NOTICE == original and prepared["text"] == original["text"]
    assert prepared["clean_text"] == NOTICE["text"].strip()
    assert prepared["text_length"] == len(prepared["clean_text"])
    print("[원문 보존]", prepared["text"] == NOTICE["text"])
    print("[정리한 글자 수]", prepared["text_length"])
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API 키: ").strip()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OpenAI API 키가 필요합니다.")
    model = ChatOpenAI(model=MODEL_NAME, reasoning_effort="none",
                       max_completion_tokens=600, timeout=30, max_retries=0,
                       use_responses_api=False)
    chain = build_chain(model)
    result = chain.invoke(NOTICE)
    assert result["document_id"] == "notice-014"
    assert NOTICE == original and result["text"] == original["text"]
    assert result["clean_text"] == prepared["clean_text"]
    assert result["text_length"] == prepared["text_length"]
    assert set(result["analysis"]) == {"summary", "keywords"}
    assert all(value.strip() for value in result["analysis"].values())
    print("[전체 체인]", type(chain).__name__)
    print("[요약]", result["analysis"]["summary"])
    print("[검색어]", result["analysis"]["keywords"])


if __name__ == "__main__":
    main()