# %% 준비
import getpass
import json
import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

load_dotenv()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
REQUEST = "VPN 접속 시 인증서 오류가 납니다. 담당자의 확인을 요청합니다."
# 복구 경로를 확인하기 위해 제공한 고정 오류 문자열이며 모델의 실제 응답이 아닙니다.
BROKEN_OUTPUT = '{"category":"기타","needs_agent":false}'
PROMPT = ChatPromptTemplate.from_messages([
    ("system", "사내 문의를 접속, 문서, 계정 중 하나로 분류하세요. "
               "VPN 연결 문제는 접속입니다. summary는 문의의 한 문장 요약이며, "
               "담당자 확인을 요청한 경우 needs_agent를 true로 지정하세요."),
    ("human", "{request}"),
])
REPAIR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "원래 문의에 맞춰 실패한 출력을 JSON 객체 하나로 다시 작성하세요. "
               "VPN 문제는 접속으로, 담당자 확인 요청은 needs_agent=true로 분류하세요. "
               "설명을 덧붙이지 마세요.\n요구 형식:\n{format_instructions}"),
    ("human", "원래 문의: {request}\n실패한 출력: {broken_output}"),
])

# %% 구현
class Ticket(BaseModel):
    # TODO 1: 표에 맞춰 category, summary, needs_agent 세 필드의 스키마를 정의하세요.
    category: Literal["접속", "문서", "계정"] = Field(
        description="문서의 종류"
    )

    summary: str = Field(
        min_length=1,
        description="문의 내용을 한 문장으로 요약한 내용"
    )

    needs_agent: bool = Field(
        default=False,
        description="담당자의 확인이 필요한지 여부"
    )

def try_parse(parser, raw):
    # TODO 2: Parser 성공 객체 또는 실패를 뜻하는 None을 반환하세요.
    try:
        return parser.parse(raw)
    except OutputParserException:
        return None

def repair_once(parser, repair_chain, request, raw):
    # TODO 3: 첫 검증이 실패할 때만 한 번 수정하고 같은 Parser의 결과와 횟수를 반환하세요.
    parsed = try_parse(parser, raw)

    if parsed is not None:
        return parsed, 0

    repaired_raw = repair_chain.invoke({
        "request": request,
        "broken_output": raw,
        "format_instructions": parser.get_format_instructions(),
    })

    repaired = try_parse(parser, repaired_raw)

    return repaired, 1

def explain_error(raw):
    # 검증 위치를 짧게 보여 주는 제공 함수입니다. 원문·오류 전문은 출력하지 않습니다.
    try:
        Ticket.model_validate(json.loads(raw))
    except json.JSONDecodeError:
        return "JSON 문법 오류"
    except ValidationError as error:
        first = error.errors(include_input=False)[0]
        return f"{first['loc'][0]}: {first['type']}"
    return "검증 성공"

# %% 결과 확인
def main():
    parser = PydanticOutputParser(pydantic_object=Ticket)
    local = parser.parse('{"category":"문서","summary":"문서 위치 문의"}')
    assert local.needs_agent is False
    print("[로컬 기본값]", local.needs_agent)
    for raw in ['{"category":"접속"}', BROKEN_OUTPUT, '{"category":"접속" "summary":"문의"}']:
        assert try_parse(parser, raw) is None
        print("[검증 실패]", explain_error(raw))
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API 키: ").strip()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OpenAI API 키가 필요합니다.")
    model = ChatOpenAI(model=MODEL_NAME, reasoning_effort="none",
                       max_completion_tokens=600, timeout=30, max_retries=0,
                       use_responses_api=False)
    native_chain = PROMPT | model.with_structured_output(Ticket)
    native = native_chain.invoke({"request": REQUEST})
    assert isinstance(native, Ticket)
    print("[실제 구조화 출력]", native.model_dump())
    repair_chain = REPAIR_PROMPT | model | StrOutputParser()
    final, repair_count = repair_once(parser, repair_chain, REQUEST, BROKEN_OUTPUT)
    assert repair_count == 1
    print("[수정 요청 횟수]", repair_count)
    if final is None:
        print("[최종 결과] 재검증 실패 · 분류 결과를 사용하지 않습니다.")
    else:
        print("[수정 후 검증]", type(final).__name__)
        print("[수정 결과]", final.model_dump())


if __name__ == "__main__":
    main()