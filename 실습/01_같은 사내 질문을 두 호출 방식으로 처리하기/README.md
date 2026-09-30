## 문제 상황

사내 문서를 바탕으로 직원의 질문에 답하는 Private LLM 서비스를 준비하고 있습니다. 지금은 문서 검색이나 대화 저장을 붙이기 전에, 안내문 한 개와 질문 한 개를 모델에 보내는 기본 기능을 확인하려고 합니다.

담당자는 OpenAI SDK로 작성한 기존 코드와 LangChain으로 나눈 코드를 함께 검토하고 싶어 합니다. 같은 안내문·질문·답변 원칙을 사용해 두 방식으로 답변을 받고, 입력을 준비하는 부분과 응답을 꺼내는 부분이 어디인지 확인하세요. 실습에서는 가상의 안내문을 OpenAI API에 전달합니다.

## 주어진 입력과 만들 결과

| 이름 | 의미 |
| --- | --- |
| `DOCUMENT` | VPN 프로그램을 다시 실행하고, 계속 실패하면 IT지원팀에 문의하라는 안내문입니다. |
| `QUESTION` | VPN이 계속 연결되지 않는 직원의 질문입니다. |
| `SYSTEM` | 안내문에 있는 내용만 사용하고 두 문장 이내로 답하라는 공통 원칙입니다. |
| `USER_TEMPLATE` | 안내문과 질문을 각각 표시하는 문자열 양식입니다. |

최종 결과는 `direct`, `langchain` 두 키를 가진 딕셔너리입니다. 각 값은 해당 방식으로 받은 답변 문자열입니다. 두 답변의 문장은 달라도 됩니다. 안내문의 조치와 문의처가 질문에 맞게 담겼는지 확인하세요.

## 환경에서 먼저 확인할 것

실행 코드는 현재 Python 경로와 설치된 핵심 패키지 버전을 출력합니다. VS Code에서는 이 경로와 선택한 인터프리터가 프로젝트의 `.venv`를 가리키는지 확인하세요. Colab에서는 노트북 런타임의 Python 경로가 표시됩니다.

- `langchain-core`의 `langchain_core`에는 Prompt, 메시지, Parser 같은 공통 구성 요소가 있습니다.
- `langchain-openai`의 `langchain_openai`는 OpenAI 모델을 LangChain 인터페이스에 연결합니다.
- `openai`는 직접 호출에 사용하는 공식 SDK이고, `python-dotenv`의 `dotenv`는 로컬 `.env`를 읽습니다.
- `langchain`은 에이전트 등 상위 기능을 제공합니다. 이번 코드에서 사용하는 구성 요소는 `langchain-core`와 `langchain-openai`에 있습니다.

## 구현할 부분

시작 코드의 세 TODO를 채우세요. 환경 확인·키 입력·실행 예시는 제공되어 있습니다. 정답 파일은 시작 코드를 대체하는 완성본입니다.

### TODO 1. SDK로 답변 받기

`ask_direct(client, document, question)`은 준비된 OpenAI 클라이언트와 문자열 두 개를 받습니다.

1. `USER_TEMPLATE`에 안내문과 질문을 넣습니다.
2. `system` 메시지에 `SYSTEM`, `user` 메시지에 완성한 문자열을 넣고 이 순서로 전달합니다.
3. `client.chat.completions.create()`로 요청합니다. 모델은 `MODEL_NAME`, `reasoning_effort`는 `"none"`, `max_completion_tokens`는 `600`을 사용합니다.
4. 첫 응답 후보의 메시지 본문을 반환합니다. 응답 객체 자체를 반환하지 마세요.

### TODO 2. LangChain의 세 단계 연결하기

`ask_langchain(model, document, question)`은 준비된 ChatModel과 같은 안내문·질문을 받습니다.

- `ChatPromptTemplate`에서 `system`은 `SYSTEM`, `human`은 `USER_TEMPLATE`을 사용합니다.
- 템플릿에 실제 값을 넣은 메시지 목록을 Model에 전달하고, 받은 응답은 `StrOutputParser`로 변환합니다.
- 관찰할 수 있도록 원본 모델 응답과 최종 문자열을 이 순서의 튜플로 반환합니다.

이 장에서는 각 단계를 차례로 실행합니다. 두 번째 모델 호출에도 첫 번째와 같은 입력이 전달되어야 합니다.

### TODO 3. 두 결과 확인하기

`check_answers(direct_answer, chain_answer)`에서 두 값이 모두 문자열이고 공백만 있는 값이 아닌지 검사하세요. 조건을 만족하지 않으면 `ValueError`를 발생시킵니다. 정상일 때는 원문을 수정하지 않고 `{"direct": ..., "langchain": ...}` 형태로 반환합니다.

답변 두 개가 같은 문장인지 비교하는 조건은 넣지 마세요. 모델 호출은 정상 경로에서 총 두 번이며, 나머지는 환경 확인과 Python 객체 처리입니다.

# 실행결과

langchain-core: 1.5.1
langchain-openai: 1.4.1
openai: 2.48.0
python-dotenv: 1.2.2
모델: gpt-5.6-luna
Model 결과가 AIMessage인가: True
[direct] 프로그램을 다시 실행하세요. 그래도 계속 실패하면 IT지원팀에 문의하세요.
[langchain] 프로그램을 다시 실행하세요. 그래도 계속 실패하면 IT지원팀에 문의하세요.
답변 문자열 확인: True