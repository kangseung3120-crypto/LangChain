## 문제 상황

사내 Private LLM 서비스에서 같은 안내 기능을 세 곳에 사용하려고 합니다. 직원이 질문 하나를 보낼 때는 완성된 답변 하나를 받고, 운영자가 문의 두 개를 점검할 때는 결과 목록을 받습니다. 채팅 화면에서는 답변이 만들어지는 대로 내용을 보여 주어야 합니다.

세 기능에 각각 다른 체인을 만들면 답변 원칙을 바꿀 때 수정할 곳도 늘어납니다. Prompt → Model → Parser를 한 번 연결하고, 같은 체인에서 입력과 실행 방식만 바꾸어 사용하세요. 코드에는 실제 사내 자료 대신 가상의 VPN·회의실 안내가 들어 있습니다.

## 주어진 입력과 만들 결과

`INPUTS`에는 서로 독립적인 문의 두 개가 순서대로 들어 있습니다. 각 항목은 `document`, `question` 키가 있는 딕셔너리입니다.

| 위치 | 안내문 | 질문 |
| --- | --- | --- |
| `INPUTS[0]` | VPN 오류가 나면 프로그램을 다시 실행한 뒤 IT지원팀에 문의합니다. | 계속 오류가 나면 어디에 문의하는지 묻습니다. |
| `INPUTS[1]` | 회의실 신청과 취소는 사내 예약 화면에서 처리합니다. | 예약 취소 방법을 묻습니다. |

같은 체인으로 첫 문의의 단일 답변, 문의 두 개의 답변 목록, 두 번째 문의의 스트리밍 답변을 확인합니다. 목록의 위치는 입력 순서와 대응해야 합니다. 스트리밍은 화면 출력과 전체 답변 보관을 한 번의 실행에서 처리합니다.

## 구현할 부분

### TODO 1. 재사용할 체인 만들기

`build_chain(model)`은 준비된 ChatModel을 받아 `prompt`, `chain`을 이 순서로 반환합니다.

- `ChatPromptTemplate`의 `system`에는 `SYSTEM`, `human`에는 `USER_FORMAT`을 사용합니다.
- Prompt, 전달받은 Model, `StrOutputParser`를 데이터가 이동할 순서대로 연결합니다.
- 이 함수에서는 모델을 호출하지 않습니다. 입력을 고정해 답변 문자열을 반환하는 함수로 만들지 마세요.

Prompt를 함께 반환하는 것은 입력 변수와 중간 결과를 확인하기 위해서입니다. 일반적인 앱에서 항상 이 두 값을 함께 반환해야 한다는 뜻은 아닙니다.

### TODO 2. 한 건 실행과 여러 건 실행하기

`run_single_and_batch(chain, inputs)`에서 다음 두 결과를 얻으세요.

- `inputs[0]`에 대한 `invoke()`의 문자열 결과
- `inputs` 전체에 대한 `batch()`의 결과 목록

입력 개수와 결과 개수가 다르면 `ValueError`를 발생시킵니다. 정상일 때는 단일 결과와 결과 목록을 이 순서로 반환하세요. `batch()`에 딕셔너리 하나를 전달하거나, 두 문의를 하나의 긴 질문으로 합치지 마세요.

### TODO 3. 스트리밍을 표시하면서 보관하기

`show_stream(chain, input_data)`에서 `stream()`이 내보내는 조각을 순서대로 처리하세요.

- 조각이 도착할 때마다 줄바꿈 없이 바로 출력합니다. `print()`의 `end`와 `flush` 옵션을 활용하세요.
- 같은 조각을 목록에 보관하고, 종료 후 빈 문자열을 구분자로 합쳐 전체 답변을 반환합니다.
- 조각 사이의 공백과 줄바꿈은 그대로 보존합니다. 출력용과 저장용으로 `stream()`을 두 번 실행하지 마세요.

# 실행결과

체인 종류: RunnableSequence
입력 점검: document와 question 키가 있는 dict가 필요합니다.
Prompt 결과: ChatPromptValue
Model은 AIMessage / Parser는 문자열: True True
Traceback (most recent call last):
  File "C:\Users\rkdtm\Desktop\LLM\LangChain\실습\03_사내 안내 체인을 세 실행 방식으로 사용하기\실습.py", line 90, in <module>
    main()
  File "C:\Users\rkdtm\Desktop\LLM\LangChain\실습\03_사내 안내 체인을 세 실행 방식으로 사용하기\실습.py", line 78, in main
    single, results = run_single_and_batch(chain, INPUTS)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\rkdtm\Desktop\LLM\LangChain\실습\03_사내 안내 체인을 세 실행 방식으로 사용하기\실습.py", line 40, in run_single_and_batch
    results = chain.invoke_batch(inputs)
              ^^^^^^^^^^^^^^^^^^
  File "C:\Users\rkdtm\Desktop\LLM\LangChain\실습\03_사내 안내 체인을 세 실행 방식으로 사용하기\.venv\Lib\site-packages\pydantic\main.py", line 1042, in __getattr__
    raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
AttributeError: 'RunnableSequence' object has no attribute 'invoke_batch'
PS C:\Users\rkdtm\Desktop\LLM\LangChain\실습\03_사내 안내 체인을 세 실행 방식으로 사용하기> uv run python 실습.py
체인 종류: RunnableSequence
입력 점검: document와 question 키가 있는 dict가 필요합니다.
Prompt 결과: ChatPromptValue
Model은 AIMessage / Parser는 문자열: True True
[invoke] IT지원팀에 문의하세요.
[batch] VPN 오류가 계속 나면 어디에 문의하나요? → IT지원팀에 문의하세요.
[batch] 회의실 예약을 취소하려면 어떻게 하나요? → 사내 예약 화면에서 취소하면 됩니다.
[stream]
사내 예약 화면에서 취소할 수 있습니다.결과 개수 / 비어 있지 않은 답변: 2 True