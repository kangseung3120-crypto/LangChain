# %% 준비
import getpass
import os

from dotenv import load_dotenv
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import (
    CommaSeparatedListOutputParser, JsonOutputParser, StrOutputParser,
)
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
DOCUMENT = "VPN 연결이 끊기면 프로그램을 다시 실행하세요. 계속 실패하면 IT지원팀에 문의하세요."
AUDIENCE = "처음 출근한 직원"
USER_FORMAT = "대상: {audience}\n안내문: {document}"
RULES = (
    "사내 안내 카드를 만드세요. 제공된 안내문에 있는 내용만 사용하세요. "
    "summary는 한 문장 요약, steps는 수행 순서대로 조치 두 개를 쉼표로 나눈 문자열입니다. "
    "steps의 각 조치 안에는 쉼표를 넣지 마세요. 두 값은 모두 비어 있지 않은 문자열이어야 합니다. "
    "summary와 steps 키만 가진 JSON 객체 하나를 반환하세요.\n"
    "전체 응답 형식: {json_format}\nsteps 문자열 내부 형식: {list_format}"
)

# %% 구현
def make_messages(document, audience):
    # 문자열 양식을 먼저 채운 뒤 human 역할의 본문으로 넣습니다.
    text_template = PromptTemplate.from_template(USER_FORMAT)
    chat_template = ChatPromptTemplate.from_messages(
        [("system", RULES), ("human", "{user_text}")]
    )
    # TODO 1: 입력 문자열과 두 Parser의 형식 안내를 채운 뒤 user_text와 messages를 반환하세요.
    json_parser = JsonOutputParser() # json 형식을 알려주는 Parser를 만든 것.
    list_parser = CommaSeparatedListOutputParser() # 쉼표로 구분된 문자열을 리스트로 바꾸는 Parser.

    user_text = text_template.format(
        document=document,
        audience=audience,
    )

    json_format = json_parser.get_formet_instructions() 
    list_format = list_parser.get_format_instructions() 

    messages = chat_template.format_messages(
        user_text=user_text,
        json_format=json_format,
        list_format=list_format,
    )
    return user_text, messages


def read_card(message):
    # TODO 2: 문자열과 JSON을 변환·검사하고 조치 목록을 만들어 세 값을 반환하세요.
    str_parser = StrOutputParser()
    json_parser = JsonOutputParser()
    list_parser = CommaSeparatedListOutputParser()

    raw_text = str_parser.invoke(message)
    card = json_parser.invoke(raw_text)

    if not isinstance(card, dict):
        raise ValueError("응답이 딕셔너리 형식이 아닙니다.")

    if "summary" not in card or "steps" not in card:
        raise ValueError("summary와 steps 키가 필요합니다.")
    
    if not isinstance(card["summary"], str) or not card["summary"].strip():
        raise ValueError("summary는 비어 있지 않은 문자열이어야 합니다.")
    
    if not isinstance(card["steps"], str) or not card["steps"].strip():
            raise ValueError("steps는 비어 있지 않은 문자열이어야 합니다.")

    steps = list_parser.invoke(card["steps"])

    return raw_text, card, steps

def render_card(card, steps):
    # TODO 3: 조치 개수와 빈 항목을 확인한 뒤 요약과 번호 목록을 문자열로 만드세요.
    if len(steps) != 2:
        raise ValueError("조치는 정확히 두 개여야 합니다.")

    for step in steps:
        if not isinstance(step, str) or not step.strip():
            raise ValueError("각 조치는 비어 있지 않은 문자열이어야 합니다.")

    numbered_step = "\n".join(
        f"{index}. {step}"
        for index, step in enumerate(steps, start=1)
    )

    return f"{card['summary']}\n{numbered_step}"

# %% 결과 확인
def main():
    user_text, messages = make_messages(DOCUMENT, AUDIENCE)
    print("완성된 입력:", user_text, sep="\n")
    print("메시지 역할:", [message.type for message in messages])
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API 키: ")
    if not os.environ["OPENAI_API_KEY"].strip():
        raise ValueError("API 키가 비어 있습니다.")
    model = ChatOpenAI(model=MODEL_NAME, reasoning_effort="none",
                       max_completion_tokens=600, timeout=30, max_retries=0,
                       use_responses_api=False)
    message = model.invoke(messages)
    try:
        raw_text, card, steps = read_card(message)
        print("문자열 / dict / list:", isinstance(raw_text, str), isinstance(card, dict), isinstance(steps, list))
        print(render_card(card, steps))
    except (OutputParserException, ValueError) as error:
        # 응답을 성공한 카드로 바꾸지 않고 실제 형식과 입력 지시를 비교합니다.
        print("형식 확인 필요:", type(error).__name__)
        print("받은 응답:", StrOutputParser().invoke(message))
        raise


if __name__ == "__main__":
    main()