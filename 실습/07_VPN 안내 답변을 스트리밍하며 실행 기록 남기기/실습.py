# %% 준비
import getpass
import os
import time
from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
CONTEXT = "VPN 연결 실패 시 프로그램을 다시 실행합니다. 계속 실패하면 IT 지원팀에 문의합니다."
QUESTION = "VPN 연결이 계속 실패하면 어떻게 해야 하나요?"

# %% 구현
class LocalTrace(BaseCallbackHandler):
    """한 요청의 단계 이름과 모델 측정값만 메모리에 기록합니다."""

    def __init__(self):
        self.stages = []
        self.text_events = 0
        self.usage = None
        self.elapsed_ms = None
        self.status = "ready"

    def on_chain_start(self, serialized, inputs, **kwargs):
        # 입력 원문 대신 실행 단계 이름만 남깁니다.
        self.stages.append(kwargs.get("name") or "이름 없는 체인")

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.stages.append("OpenAI 모델")
        self.started_at = time.perf_counter()
        self.text_events, self.usage = 0, None
        self.elapsed_ms, self.status = None, "running"

    def on_llm_new_token(self, token, **kwargs):
        # 빈 조각과 문자열이 아닌 값은 출력 이벤트 수에 넣지 않습니다.
        # TODO 1: 내용이 있는 문자열 이벤트만 self.text_events에 셉니다.
        if isinstance(token, str) and token:
            self.text_events += 1

    def on_llm_end(self, response, **kwargs):
        # Parser 뒤의 문자열이 아닌 모델 완료 결과에서 사용량을 읽습니다.
        # TODO 2: 모델 경과 시간, 완료 상태, 제공된 usage_metadata를 기록합니다.
        self.elapsed_ms = (time.perf_counter() - self.started_at) * 1000
        self.status = "completed"

        message = response.generations[0][0].message
        self.usage = getattr(message, "usage_metadata", None)

    def on_llm_error(self, error, **kwargs):
        self.elapsed_ms = (time.perf_counter() - self.started_at) * 1000
        self.status = f"error:{type(error).__name__}"
        # 상세 예외에는 요청 정보가 들어갈 수 있어 종류만 기록합니다.


def stream_answer(chain, payload, trace):
    # 같은 호출에서 화면 출력과 전체 답변 보관을 함께 처리합니다.
    # TODO 3: trace를 연결한 stream 한 번으로 출력·수집하고 빈 답변을 검사합니다.
    chunks = []

    for chunk in chain.stream(
        payload,
        config={
            "callbacks": [trace],
            "run_name": "VPN 안내",
        },
    ):
        chunks.append(chunk)
        print(chunk, end="", flush=True)

    print()

    answer = "".join(chunks)

    if not answer.strip():
        raise ValueError("모델이 빈 답변을 반환했습니다.")

    return answer


# %% 결과 확인
def main():
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API 키: ").strip()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OpenAI API 키를 입력해 주세요.")
    model = ChatOpenAI(model=MODEL_NAME, reasoning_effort="none", max_completion_tokens=600,
                       timeout=30, max_retries=0, use_responses_api=False, stream_usage=True)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "사내 안내 담당자입니다. 주어진 문서 안에서 한국어 두 문장으로 답하세요."),
        ("human", "문서: {context}\n질문: {question}"),
    ]).with_config(run_name="프롬프트")
    chain = prompt | model | StrOutputParser().with_config(run_name="문자열 변환")
    trace = LocalTrace()
    print("[실제 모델 스트리밍 답변]")
    try:
        answer = stream_answer(chain, {"context": CONTEXT, "question": QUESTION}, trace)
    finally:
        # 모델 오류가 나도 관측 상태를 표시하고 원래 오류는 호출자에게 전달합니다.
        print("[로컬 단계 시작]", " → ".join(trace.stages))
        print(f"[모델 상태] {trace.status} / 출력 이벤트 {trace.text_events}개")
        print("[모델 경과 ms]", trace.elapsed_ms)
        print("[사용량]", trace.usage if trace.usage is not None else "제공되지 않음")
    assert isinstance(answer, str) and answer.strip()
    assert trace.status == "completed" and trace.text_events > 0
    print("[확인] 전체 문자열 보관 완료")


if __name__ == "__main__":
    main()