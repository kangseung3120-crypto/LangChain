# %% 준비
import getpass
import os

from dotenv import load_dotenv
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

load_dotenv()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
SYSTEM_RULE = (
    "사내 IT 문의 접수를 돕습니다. 사용자가 현재 대화에서 알려 준 요청 번호와 문제만 "
    "참고하여 두 문장 이내로 답하세요. 요청 번호를 전달받지 않았다면 아직 전달받지 "
    "않았다고 말하고 번호를 물어보세요. 번호나 사내 처리 규정을 추측하지 마세요."
)
FIRST_QUESTION = "제 요청 번호는 IT-042이고 VPN 인증서 오류를 문의했습니다. 기억해 주세요."
FOLLOWUP = "제가 앞에서 알려 준 요청 번호와 문제는 무엇인가요?"

# %% 구현
def get_session_history(store, session_id):
    # TODO 1: 세션 ID를 검사하고 새 ID일 때만 history를 만든 뒤 반환하세요.
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id는 비어 있지 않은 문자열이어야 합니다.")

    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()

    return store[session_id]

def build_chain(model):
    # TODO 2: 시스템 지시·history·현재 질문 순서로 Prompt와 모델·Parser를 연결하세요.
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_RULE),
        MessagesPlaceholder("history"),
        ("human", "{question}"),
    ])

    return prompt | model | StrOutputParser()


def ask_session(chain, store, session_id, question):
    if not isinstance(question, str) or not question.strip():
        raise ValueError("질문이 비어 있습니다.")
    history = get_session_history(store, session_id)
    # TODO 3: 이전 메시지로 답한 뒤 정상 질문·답변 한 쌍만 저장하고 답변을 반환하세요.
    previous_messages = list(history.messages)

    answer = chain.invoke({
        "history": previous_messages,
        "question": question,
    })

    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("모델 답변이 비어 있습니다")

    history.add_message(HumanMessage(content=question))
    history.add_message(AIMessage(content=answer))

    return answer

# %% 결과 확인
def main():
    # main을 다시 실행하면 새 저장소로 시작합니다. 디스크에는 대화를 저장하지 않습니다.
    store = {}
    first = get_session_history(store, "employee-a")
    assert first is get_session_history(store, "employee-a")
    assert first is not get_session_history(store, "employee-b")
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API 키: ").strip()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OpenAI API 키가 필요합니다.")
    model = ChatOpenAI(model=MODEL_NAME, reasoning_effort="none",
                       max_completion_tokens=600, timeout=30, max_retries=0,
                       use_responses_api=False)
    chain = build_chain(model)
    print("[A 첫 답변]", ask_session(chain, store, "employee-a", FIRST_QUESTION))
    print("[A 후속 답변]", ask_session(chain, store, "employee-a", FOLLOWUP))
    print("[B 첫 답변]", ask_session(chain, store, "employee-b", FOLLOWUP))
    # 문장 표현과 별개로 저장 개수·역할·세션별 사용자 입력을 확인합니다.
    assert len(store["employee-a"].messages) == 4
    assert len(store["employee-b"].messages) == 2
    assert [m.type for m in store["employee-a"].messages] == ["human", "ai", "human", "ai"]
    assert store["employee-a"].messages[0].content == FIRST_QUESTION
    assert store["employee-b"].messages[0].content == FOLLOWUP
    for session_id, history in store.items():
        print(f"[{session_id}] 메시지 {len(history.messages)}개")
        print("[역할 순서]", [message.type for message in history.messages])
    print("[이력 객체 분리]", store["employee-a"] is not store["employee-b"])


if __name__ == "__main__":
    main()