# %% 준비
import getpass
import os
from typing import Literal
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, InternalServerError
from pydantic import BaseModel, Field

load_dotenv()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")


class TemporaryModelError(RuntimeError):
    """외부 요청 없이 재현하는 교육용 일시 오류입니다."""


class UserAnswer(BaseModel):
    status: Literal["ok", "degraded"]
    answer: str = Field(min_length=1)
    route: Literal["primary", "fallback"]


# 인증·입력·요금 한도 오류는 이 정책으로 해결하지 않습니다.
RECOVERABLE = (TemporaryModelError, APIConnectionError, InternalServerError)

# %% 구현
def build_policy(primary, fallback):
    # 실패 가능한 단계만 감싸고 전체 시도 횟수를 한 곳에서 관리합니다.
    # TODO 1: 최대 두 번 시도한 뒤 허용한 오류만 fallback으로 연결합니다.
    retry = RunnableLambda(primary).with_retry(
        retry_if_exception_type=RECOVERABLE,
        stop_after_attempt=2,
        wait_exponential_jitter=False,
    )

    return retry.with_fallbacks(
        [RunnableLambda(fallback)],
        exceptions_to_handle=RECOVERABLE,
    )

def fallback_answer(_):
    # 모델이 생성한 정상 답으로 보이지 않도록 상태와 경로를 함께 바꿉니다.
    # TODO 2: 기능 제한과 다음 행동을 알리는 UserAnswer를 반환합니다.
    return UserAnswer(
        status="degraded",
        route="fallback",
        answer="현재 문서 답변 기능을 사용할 수 없습니다. 자세한 안내가 필요하면 IT 지원팀에 문의해 주세요"
    )

def build_drill(failures):
    # 안쪽 두 함수와 반환한 counts는 같은 사전을 참조합니다. 새 build_drill 호출은 별도 사전을 만듭니다.
    counts = {"primary": 0, "fallback": 0}

    def primary(question):
        # 각 정책 실행의 실제 진입 수를 먼저 셉니다.
        # TODO 3: 진입 수를 세고 입력 오류와 계획된 일시 오류를 구분합니다.
        counts["primary"] += 1

        if not isinstance(question, str) or not question.strip():
            raise ValueError("질문은 비어 있지 않은 문자열이어야 합니다.")

        if counts["primary"] <= failures:
            raise TemporaryModelError("훈련용 일시 오류")

        return UserAnswer(
            status="ok",
            route="primary",
            answer="훈련용 고정 정상 결고"
        )
    
    def fallback(payload):
        counts["fallback"] += 1
        return fallback_answer(payload)

    return build_policy(primary, fallback), counts

# %% 결과 확인
def main():
    # 훈련에는 API 호출이 없습니다. 사례마다 독립된 카운터를 만듭니다.
    for case, failures, expected in [("정상", 0, (1, 0)), ("복구", 1, (2, 0)), ("장애", 3, (2, 1))]:
        drill, counts = build_drill(failures)
        result = drill.invoke("VPN 연결 방법")
        assert (counts["primary"], counts["fallback"]) == expected
        assert (result.status, result.route) == (("degraded", "fallback") if expected[1] else ("ok", "primary"))
        print(f"[고정 오류 훈련:{case}] {result.status}/{result.route} {counts}")
    drill, counts = build_drill(3)
    try:
        drill.invoke("  ")
    except ValueError:
        assert counts == {"primary": 1, "fallback": 0}
        print("[고정 오류 훈련:입력 오류] ValueError", counts)
    else:
        raise AssertionError("입력 오류가 숨겨졌습니다.")
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API 키: ").strip()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OpenAI API 키를 입력해 주세요.")
    model = ChatOpenAI(model=MODEL_NAME, reasoning_effort="none", max_completion_tokens=600,
                       timeout=30, max_retries=0, use_responses_api=False)
    prompt = ChatPromptTemplate.from_template("문서: VPN은 프로그램 재실행 후에도 실패하면 IT 지원팀에 문의합니다.\n질문: {question}\n문서 안에서 한 문장으로 답하세요.")

    def live_primary(messages):
        text = StrOutputParser().invoke(model.invoke(messages)).strip()
        return UserAnswer(status="ok", route="primary", answer=text)

    # Prompt 구성은 Retry 바깥에서 한 번만 끝냅니다.
    messages = prompt.invoke({"question": "VPN이 계속 실패하면 누구에게 문의하나요?"})
    result = build_policy(live_primary, fallback_answer).invoke(messages)
    print("[실제 API 경로]", result.model_dump())


if __name__ == "__main__":
    main()