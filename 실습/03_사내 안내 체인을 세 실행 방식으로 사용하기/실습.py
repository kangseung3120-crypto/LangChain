# %% 준비
import getpass
import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
SYSTEM = "사내 안내 도우미입니다. 안내문에 있는 내용만 사용해 질문에 두 문장 이내로 답하세요."
USER_FORMAT = "안내문: {document}\n질문: {question}"
# 두 문의는 서로 독립적이며 앞선 질문의 답변을 기억할 필요가 없습니다.
INPUTS = [
    {"document": "VPN 오류가 나면 프로그램을 다시 실행한 뒤 IT지원팀에 문의하세요.",
     "question": "VPN 오류가 계속 나면 어디에 문의하나요?"},
    {"document": "회의실은 사내 예약 화면에서 신청하고 취소도 같은 화면에서 처리합니다.",
     "question": "회의실 예약을 취소하려면 어떻게 하나요?"},
]

# %% 구현
def build_chain(model):
    # TODO 1: Prompt, Model, Parser를 조립하고 prompt와 chain을 반환하세요.
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM),
            ("human", USER_FORMAT),
        ]
    )

    chain = prompt | model | StrOutputParser()

    return prompt, chain

def run_single_and_batch(chain, inputs):
    # TODO 2: 한 건과 여러 건을 실행하고 결과 개수를 확인한 뒤 두 결과를 반환하세요.
    single = chain.invoke(inputs[0])

    results = chain.batch(inputs)

    if len(inputs) != len(results):
        raise ValueError("입력 개수와 결과 개수가 다릅니다.")

    return single, results

def show_stream(chain, input_data):
    # TODO 3: 한 stream의 조각을 화면과 목록에 함께 처리하고 전체 문자열을 반환하세요.
    chunks = []
    for chunk in chain.stream(input_data):
        print(chunk, end="", flush=True)
        chunks.append(chunk)

    return "".join(chunks)

# %% 결과 확인
def main():
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API 키: ")
    if not os.environ["OPENAI_API_KEY"].strip():
        raise ValueError("API 키가 비어 있습니다.")
    model = ChatOpenAI(model=MODEL_NAME, reasoning_effort="none",
                       max_completion_tokens=600, timeout=30, max_retries=0,
                       use_responses_api=False)
    prompt, chain = build_chain(model)
    print("체인 종류:", type(chain).__name__)
    # 잘못된 입력은 모델 단계에 도달하기 전에 Prompt에서 중단됩니다.
    try:
        prompt.invoke("VPN 오류")
    except TypeError:
        print("입력 점검: document와 question 키가 있는 dict가 필요합니다.")
    # 제공된 관찰 코드: 앞 장의 순차 실행으로 중간 객체를 확인합니다.
    prepared = prompt.invoke(INPUTS[0])
    message = model.invoke(prepared)
    debug_answer = StrOutputParser().invoke(message)
    print("Prompt 결과:", type(prepared).__name__)
    print("Model은 AIMessage / Parser는 문자열:", isinstance(message, AIMessage), isinstance(debug_answer, str))
    single, results = run_single_and_batch(chain, INPUTS)
    print("[invoke]", single)
    for data, answer in zip(INPUTS, results):
        print(f"[batch] {data['question']} → {answer}")
    print("[stream]")
    streamed = show_stream(chain, INPUTS[1])
    all_answers = [debug_answer, single, *results, streamed]
    assert all(isinstance(answer, str) and answer.strip() for answer in all_answers)
    print("결과 개수 / 비어 있지 않은 답변:", len(results), True)


if __name__ == "__main__":
    main()