# %% 준비
import getpass
import os
import time
from typing import Literal
from dotenv import load_dotenv
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, InternalServerError
from pydantic import BaseModel, Field

load_dotenv()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
DOCUMENTS = [
    Document(page_content="VPN은 프로그램 재실행 후에도 실패하면 IT 지원팀에 문의합니다.", metadata={"id": "it-01", "keyword": "vpn"}),
    Document(page_content="교육비는 팀장 승인 후 신청서를 교육 담당자에게 제출합니다.", metadata={"id": "hr-01", "keyword": "교육비"}),
]

class SourceAnswer(BaseModel):
    answer: str = Field(min_length=1)
    sources: list[str]

class QAResponse(SourceAnswer):
    status: Literal["grounded", "not_found", "degraded"]
    route: Literal["primary", "local", "fallback"]

class TemporaryModelError(RuntimeError):
    """모델 호출 직전에 발생시키는 고정 오류 훈련용 예외입니다."""

# %% 구현
def build_app(model, observer=print):
    # 반환한 ask를 여러 번 호출하면 이 사전을 계속 씁니다. 새 build_app 호출은 빈 이력으로 시작합니다.
    histories = {}
    retriever = RunnableLambda(lambda q: [d for d in DOCUMENTS if d.metadata["keyword"] in q.lower()])
    parser = PydanticOutputParser(pydantic_object=SourceAnswer)
    # TODO 1: system 규칙, history 메시지, context/question, Parser 형식을 연결합니다.
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "현재 제공된 문서만 근거로 한국어 한 문장으로 답하세요."
            "답변에 사용한 문서 ID를 sources에 넣으세요.\n"
            "{format}"
        ),
        (
            "human",
            "현재 문서:\n{context}\n\n"
            "현재 질문:\n{question}"
        ),
    ]).partial(
        format=parser.get_format_instructions()
    )

    def ask(session_id, question, failures=0):
        if not session_id.strip() or not question.strip():
            raise ValueError("세션과 질문을 입력해 주세요.")
        started = time.perf_counter()
        count = {"attempts": 0, "usage": None}
        # 문서가 없으면 모델 정책에 진입하지 않습니다.
        found = retriever.invoke(question)
        if not found:
            result = QAResponse(status="not_found", route="local", answer="관련 문서를 찾지 못했습니다.", sources=[])
        else:
            history = histories.setdefault(session_id, InMemoryChatMessageHistory())
            context = "\n".join(f"[{d.metadata['id']}] {d.page_content}" for d in found)

            def primary(messages):
                count["attempts"] += 1
                if count["attempts"] <= failures:
                    raise TemporaryModelError("계획된 모델 장애")
                message = model.invoke(messages)
                count["usage"] = message.usage_metadata
                parsed = parser.invoke(message)
                return QAResponse(**parsed.model_dump(), status="grounded", route="primary")

            def fallback(_):
                return QAResponse(status="degraded", route="fallback", answer="현재 답변을 만들 수 없습니다. 담당 부서에 문의해 주세요.", sources=[])

            recoverable = (TemporaryModelError, APIConnectionError, InternalServerError)
            policy = RunnableLambda(primary).with_retry(retry_if_exception_type=recoverable,
                       stop_after_attempt=2, wait_exponential_jitter=False).with_fallbacks(
                       [RunnableLambda(fallback)], exceptions_to_handle=recoverable)
            # 현재 세션 대화와 현재 검색 문서를 별도 값으로 넣습니다.
            # TODO 2: 최근 네 메시지와 검색 근거로 Prompt를 만든 뒤 정책을 한 번 실행합니다.
            history_text = "\n".join(
                f"{message.type}: {message.content}"
                for message in history.messages[-4:]
            )

            messages = prompt.invoke({
                "question": question,
                "context": context,
                "history": history_text,
            })

            result = policy.invoke(messages)

            if result.status == "grounded":
                # 형식과 실제 출처를 확인한 후에만 두 메시지를 함께 저장합니다.
                # TODO 3: 답변과 검색 출처를 검증한 뒤 질문·답변을 현재 세션에 함께 저장합니다.
                if result.status == "grounded":
                    if not result.answer.strip():
                        raise ValueError("답변이 비어 있습니다.")

                    if not result.sources:
                        raise ValueError("출처가 없습니다.")

                    found_ids = {d.metadata["id"] for d in found}

                    if not set(result.sources).issubset(found_ids):
                        raise ValueError("검색 결과에 없는 출처가 포함되어 있습니다.")

                    history.add_messages([
                        HumanMessage(content=question),
                        AIMessage(content=result.answer),
                    ])
                    
        record = {"session": session_id, "status": result.status, "route": result.route,
                  "attempts": count["attempts"], "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                  "token_usage": count["usage"] if count["usage"] is not None else "not_available"}
        try:
            observer(record)
        except Exception:
            pass  # 출력이 실패한 곳에 오류 안내를 다시 쓰지 않고 결과를 반환합니다.
        return result

    return ask, histories

# %% 결과 확인
def main():
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API 키: ").strip()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OpenAI API 키를 입력해 주세요.")
    model = ChatOpenAI(model=MODEL_NAME, reasoning_effort="none", max_completion_tokens=600,
                       timeout=30, max_retries=0, use_responses_api=False)
    ask, histories = build_app(model)
    cases = [("a", "VPN이 계속 실패하면 어디에 문의하나요?", 0, "grounded"),
             ("a", "VPN 문의 대상을 다시 짧게 알려 주세요.", 0, "grounded"),
             ("b", "주차 등록 방법은?", 0, "not_found"),
             ("c", "교육비는 어떻게 신청하나요?", 1, "grounded"),
             ("d", "교육비 신청 방법은?", 3, "degraded")]
    for session, question, failures, expected in cases:
        result = ask(session, question, failures)
        assert result.status == expected
        print("[답변]", result.model_dump())
    assert len(histories["a"].messages) == 4 and len(histories["c"].messages) == 2
    assert "b" not in histories and not histories["d"].messages
    print("[확인] 세션 분리 및 검증 후 저장 완료")


if __name__ == "__main__":
    main()