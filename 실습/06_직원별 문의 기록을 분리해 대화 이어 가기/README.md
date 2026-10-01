## 문제 · 두 직원의 IT 문의 대화를 분리해서 이어 가기

Private LLM 문의 도우미가 직원이 앞서 알려 준 요청 번호를 다음 질문에서도 사용할 수 있어야 합니다. 같은 직원의 기록은 이어서 읽되 다른 직원의 기록이 Prompt에 섞이면 안 됩니다.

직원 A는 요청 번호와 문제를 알려 준 뒤 같은 대화에서 다시 묻습니다. 직원 B는 아무 정보도 전달하지 않은 상태에서 같은 후속 질문을 보냅니다. 이 두 경우를 하나의 체인과 세션 저장소로 처리하세요.

### 주어진 대화

| 순서 | session_id | 사용자 메시지 |
| --- | --- | --- |
| 1 | `employee-a` | 제 요청 번호는 IT-042이고 VPN 인증서 오류를 문의했습니다. 기억해 주세요. |
| 2 | `employee-a` | 제가 앞에서 알려 준 요청 번호와 문제는 무엇인가요? |
| 3 | `employee-b` | 제가 앞에서 알려 준 요청 번호와 문제는 무엇인가요? |

요청 번호와 내용은 실습을 위한 가상 데이터입니다. 시스템 지시는 이미 제공되어 있으며, 현재 대화에서 받은 정보만 사용하고 번호가 없으면 다시 물어보도록 되어 있습니다.

세션 저장소는 `{session_id: InMemoryChatMessageHistory 객체}` 형태의 Python 딕셔너리입니다. 저장소를 나누는 기능만 구현하며 별도의 로그인이나 권한 시스템은 만들지 않습니다.

### 만들어야 할 동작

- 같은 `session_id`는 기존 history 객체를 다시 사용합니다.
- 다른 `session_id`는 다른 history 객체를 사용합니다.
- 모델에는 시스템 지시, 해당 세션의 이전 메시지, 현재 질문 순으로 전달합니다.
- 답변을 정상적으로 받은 뒤에만 현재 질문과 답변을 그 세션에 저장합니다.
- 한 번의 대화는 `HumanMessage`, `AIMessage` 순서의 두 메시지입니다.

### 직접 작성할 부분

**TODO 1 · `get_session_history(store, session_id)`**

문자열이 아니거나 공백뿐인 세션 ID는 `ValueError`로 거부하세요. 처음 받은 ID일 때만 빈 `InMemoryChatMessageHistory`를 저장한 뒤 해당 객체를 반환합니다. 기존 ID의 기록을 새 객체로 덮어쓰면 안 됩니다.

**TODO 2 · `build_chain(model)`**

`SYSTEM_RULE`, `MessagesPlaceholder("history")`, 현재 질문 `"{question}"`을 이 순서로 넣어 `ChatPromptTemplate`을 만드세요. 전달받은 모델과 `StrOutputParser`까지 연결한 Runnable을 반환합니다. Placeholder는 문자열 요약이 아니라 역할이 있는 메시지 목록을 받습니다.

**TODO 3 · `ask_session()`의 호출과 기록 갱신**

앞에서 가져온 `history`의 메시지를 `list(history.messages)`로 복사하여 체인의 `history` 키에 넣으세요. 현재 질문은 별도의 `question` 키에 넣어 호출합니다.

답변이 문자열이 아니거나 공백뿐이면 `ValueError`를 발생시키세요. 정상 답변인 경우에만 현재 질문과 답변을 메시지 객체로 만들어 순서대로 추가하고 답변 문자열을 반환합니다. 모델 호출 자체가 실패하면 저장 코드에 도달하지 않아야 합니다.

### 코드에서 확인할 실행 계약

실습은 history 조회·주입·갱신을 직접 구현합니다. 기존 코드에서 보이는 `RunnableWithMessageHistory`는 이 작업을 대신 처리하던 래퍼이며 현재 지정 버전에서는 폐기 예정입니다. 기존 계약과 이번 함수의 관계만 아래처럼 읽어 두세요.

| 기존 래퍼에서 지정하던 값 | 이번 코드에서 대응하는 위치 |
| --- | --- |
| 감싸는 기본 Runnable | `build_chain(model)`이 반환한 체인 |
| 세션 history 조회 함수 | `get_session_history(store, session_id)` |
| `input_messages_key="question"` | 호출 입력의 `question` 키 |
| `history_messages_key="history"` | Placeholder 이름과 호출 입력의 `history` 키 |
| `configurable.session_id` | `ask_session()`에 직접 전달하는 `session_id` 인자 |

별도의 래퍼나 영구 저장소를 추가할 필요는 없습니다. 기본 실행은 표의 세 대화를 차례로 처리하여 실제 모델을 세 번 호출합니다.

# 실행결과

[A 첫 답변] 요청 번호 IT-042와 VPN 인증서 오류 문의를 확인했습니다.
[A 후속 답변] 요청 번호는 IT-042이며, 문제는 VPN 인증서 오류입니다.
[B 첫 답변] 이 대화에서는 요청 번호와 문제를 아직 전달받지 않았습니다. 요청 번호와 문제를 알려 주세요.
[employee-a] 메시지 4개
[역할 순서] ['human', 'ai', 'human', 'ai']
[employee-b] 메시지 2개
[역할 순서] ['human', 'ai']
[이력 객체 분리] True