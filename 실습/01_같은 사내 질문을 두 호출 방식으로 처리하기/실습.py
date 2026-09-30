# %% 준비
import getpass
import os
import sys
from importlib.metadata import version

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from openai import OpenAI

load_dotenv()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
# 실제 사내 자료 대신 실습용으로 만든 안내문을 사용합니다.
DOCUMENT = "VPN 연결이 끊기면 프로그램을 다시 실행하세요. 계속 실패하면 IT지원팀에 문의하세요."
QUESTION = "VPN이 계속 연결되지 않으면 어떻게 해야 하나요?"
SYSTEM = "사내 안내 도우미입니다. 제공된 안내문만 근거로 질문에 두 문장 이내로 답하세요."
USER_TEMPLATE = "안내문: {document}\n질문: {question}"

# %% 구현
def ask_direct(client, document, question):
    # 두 방식이 같은 입력을 사용해야 코드 구조를 비교할 수 있습니다.
    user_text = USER_TEMPLATE.format(document=document, question=question)
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_text}]
    response = client.chat.completions.create(
        model=MODEL_NAME, messages=messages,
        reasoning_effort="none", max_completion_tokens=600,
    )
    # SDK 응답은 여러 후보를 담는 객체이므로 첫 후보의 본문을 꺼냅니다.
    return response.choices[0].message.content


def ask_langchain(model, document, question):
    # 공통 원칙과 바뀌는 입력을 서로 다른 역할로 보존합니다.
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM), ("human", USER_TEMPLATE)]
    )
    messages = prompt.format_messages(document=document, question=question)
    message = model.invoke(messages)
    answer = StrOutputParser().invoke(message)
    # 관찰에 사용할 원본 AIMessage와 화면용 문자열을 함께 반환합니다.
    return message, answer


def check_answers(direct_answer, chain_answer):
    # 표현의 일치가 아니라 화면에 표시 가능한 답변인지를 확인합니다.
    for answer in (direct_answer, chain_answer):
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("두 방식 모두 비어 있지 않은 문자열 답변이 필요합니다.")
    return {"direct": direct_answer, "langchain": chain_answer}

# %% 결과 확인
def main():
    print("Python:", sys.executable)
    for package in ("langchain-core", "langchain-openai", "openai", "python-dotenv"):
        print(f"{package}: {version(package)}")
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API 키: ")
    if not os.environ["OPENAI_API_KEY"].strip():
        raise ValueError("API 키가 비어 있습니다.")
    print("모델:", MODEL_NAME)
    # 객체 생성은 요청을 보내지 않습니다. 위 두 함수가 각각 한 번 호출합니다.
    model = ChatOpenAI(model=MODEL_NAME, reasoning_effort="none",
                       max_completion_tokens=600, timeout=30, max_retries=0,
                       use_responses_api=False)
    with OpenAI(timeout=30, max_retries=0) as client:
        direct = ask_direct(client, DOCUMENT, QUESTION)
    message, chained = ask_langchain(model, DOCUMENT, QUESTION)
    results = check_answers(direct, chained)
    assert isinstance(message, AIMessage)
    print("Model 결과가 AIMessage인가:", isinstance(message, AIMessage))
    for name, answer in results.items():
        print(f"[{name}] {answer}")
    print("답변 문자열 확인:", all(isinstance(value, str) for value in results.values()))


if __name__ == "__main__":
    main()