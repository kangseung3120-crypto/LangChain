## 문제: 사내 문서 Q&A의 마지막 연결 완성하기

사내 Private LLM 서비스에 VPN과 교육비 안내 문서를 연결하고 있습니다. 검색과 모델 호출은 각각 동작하지만, 통합 과정에서 다음 문제가 생겼습니다. 문서가 없는 질문에도 모델을 호출하고, 다른 세션의 대화를 섞거나, 모델이 만든 출처 ID를 확인하지 않은 채 답변을 저장할 수 있습니다.

제공된 작은 앱의 연결 부분을 완성하세요. 현재 질문으로 문서를 찾고, 현재 세션의 최근 대화와 함께 모델에 전달한 뒤, 구조화 응답의 본문과 출처를 확인하고 저장해야 합니다. 검색 결과가 없거나 모델을 사용할 수 없는 경우도 같은 응답 형식으로 종료합니다.

문서와 질문은 모두 가상의 업무 사례입니다. 실제 답변 생성에는 OpenAI API를 사용합니다. 검색은 코드 안의 문서 두 개를 대상으로 하므로 별도의 벡터 데이터베이스나 임베딩 호출은 필요하지 않습니다.

### 주어진 문서와 앱의 범위

| 문서 ID | 검색 키워드 | 본문 내용 |
| --- | --- | --- |
| `it-01` | `vpn` | 프로그램 재실행 후에도 VPN이 실패하면 IT 지원팀에 문의 |
| `hr-01` | `교육비` | 팀장 승인 후 신청서를 교육 담당자에게 제출 |

제공된 Retriever는 질문에 키워드가 포함된 문서를 찾습니다. `VPN`과 `vpn`은 같은 키워드로 처리합니다. 다른 표현의 의미까지 이해하는 검색기는 아니므로 예제 질문에는 검색 키워드가 들어 있습니다.

문서 검색, Prompt·Model·Parser, 구조화 응답, 세션 기록, 제한된 Retry·Fallback, 로컬 관측은 이 앱의 기본 기능입니다. 원격 관측 계정과 영구 저장소는 추가하지 않습니다. 세션 기록은 같은 앱 객체가 살아 있는 동안 메모리에만 남습니다.

### 단계마다 받는 값과 반환하는 값

| 단계 | 입력 | 결과와 책임 |
| --- | --- | --- |
| 입력 확인 | `session_id`, `question` | 비어 있는 값을 먼저 거절 |
| 문서 검색 | 현재 질문 | `Document` 목록. 0건이면 모델 호출 없이 종료 |
| 대화 조회 | 현재 `session_id` | 현재 세션의 최근 메시지 목록 |
| Prompt 구성 | 현재 문서, 현재 질문, 최근 대화 | 모델에 보낼 메시지 목록 |
| 모델 정책 | 구성된 메시지 | 제한된 재시도 또는 기능 저하 결과 |
| 구조화·출처 검증 | 모델 응답, 검색 문서 ID | 형식과 업무 조건을 통과한 답변 |
| 대화 저장 | 검증된 질문·답변 | 해당 세션에 메시지 두 개 추가 |
| 로컬 관측·표시 | 최종 상태와 실행 정보 | 경로·진입 수·측정값과 검증 완료 답변 표시 |

관측 레코드는 모델 경로만이 아니라 검색 0건과 Fallback 경로도 같은 필드로 표시합니다. 질문·답변 원문은 관측 레코드에 넣지 않고, 답변 출력에서 따로 보여 줍니다.

### 응답 형식

모델은 제공된 `SourceAnswer` 형식의 `answer`와 `sources`를 생성합니다. 앱은 처리한 경로에 따라 `status`와 `route`를 붙여 `QAResponse`로 반환합니다. 경로를 모델에게 선택하도록 맡기지 않습니다.

| 상황 | `status` | `route` | 출처와 저장 |
| --- | --- | --- | --- |
| 문서 기반 정상 답변 | `grounded` | `primary` | 실제 검색 문서의 ID가 하나 이상 필요. 검증 후 저장 |
| 검색 결과 0건 | `not_found` | `local` | 출처 없음. 모델 호출과 세션 생성·저장 생략 |
| 모델 시도 소진 | `degraded` | `fallback` | 출처 없음. 제한 안내 반환, 메시지 저장 생략 |

Pydantic Parser는 출력 형식을 검사하지만 문서가 실제 검색됐는지는 알 수 없습니다. `sources`를 검색 결과와 대조하는 코드를 별도로 완성해야 합니다. 잘못된 형식이나 출처는 오류로 전달하며 정상 이력에 저장하지 않습니다.

### 완성할 부분

**TODO 1 — 문서와 대화를 구분하는 Prompt 구성**

`ChatPromptTemplate.from_messages()`로 다음 세 부분을 구성하세요.

1. `system`: 현재 문서만 근거로 한국어 한 문장으로 답하고, 사용한 문서 ID를 `sources`에 넣도록 안내합니다. 출력 형식을 넣을 `{format}`도 포함합니다.
2. `MessagesPlaceholder("history")`: 현재 세션의 메시지를 역할 그대로 넣습니다.
3. `human`: 현재 문서 `{context}`와 현재 질문 `{question}`을 구분해 표시합니다.

마지막에 `.partial()`을 사용해 `format`에 `parser.get_format_instructions()`를 고정합니다. Prompt의 표현은 바꿔도 되지만 세 변수와 출력 형식 지시는 유지해야 합니다.

**TODO 2 — Prompt 입력과 모델 정책 연결**

현재 위치에는 `question`, 문서를 합친 `context`, 현재 세션의 `history` 객체가 준비되어 있습니다. `question`, `context`, `history` 키를 가진 입력 딕셔너리를 만드세요. `history`에는 `history.messages`의 최근 네 메시지만 넣습니다.

이 딕셔너리로 Prompt를 한 번 실행해 `messages`를 만들고, 준비된 `policy`를 한 번 실행해 `result`를 받습니다. `result`는 `QAResponse`입니다. 대화를 조회할 때 전체 `histories` 딕셔너리를 전달하지 마세요.

**TODO 3 — 본문과 출처를 검증한 뒤 저장**

`grounded` 경로 안에서 다음 조건을 확인하세요.

- `result.answer`가 공백뿐이면 오류입니다.
- `result.sources`가 비어 있으면 오류입니다.
- 출처 중 하나라도 현재 `found` 문서의 `metadata["id"]` 집합에 없으면 오류입니다. 집합의 `issubset()`을 활용할 수 있습니다.

하나라도 어기면 `ValueError`를 발생시킵니다. 모두 통과한 뒤에만 `history.add_messages()`로 현재 질문의 `HumanMessage`와 답변의 `AIMessage`를 함께 저장하세요. 먼저 저장한 뒤 검증하는 순서로 바꾸지 않습니다.

### 제공된 오류 훈련 읽기

`failures`는 모델 단계에 진입했을 때 처음 몇 번을 계획된 오류로 끝낼지 정합니다. 오류는 실제 API 요청 전에 발생합니다. `0`은 추가 장애 없음, `1`은 첫 진입 실패 뒤 실제 모델 호출, `3`은 허용된 두 진입 모두 실패해 고정 Fallback으로 끝나는 사례입니다.

Retry는 최초 진입을 포함해 최대 두 번입니다. 실제 연결·서버 오류도 같은 제한 정책을 사용하고 SDK 자동 Retry는 꺼져 있습니다. 인증·입력·응답 검증 오류는 이 정책으로 숨기지 않습니다. Prompt 구성과 대화 저장은 Retry 범위 밖에 있습니다.

# 실행결과

{'session': 'a', 'status': 'grounded', 'route': 'primary', 'attempts': 1, 'latency_ms': 2179.1, 'token_usage': {'input_tokens': 260, 'output_tokens': 25, 'total_tokens': 285, 'input_token_details': {'audio': 0, 'cache_read': 0, 'cache_creation': 0}, 'output_token_details': {'audio': 0, 'reasoning': 0}}}
[답변] {'answer': 'VPN이 계속 실패하면 IT 지원팀에 문의합니다.', 'sources': ['it-01'], 'status': 'grounded', 'route': 'primary'}
{'session': 'a', 'status': 'grounded', 'route': 'primary', 'attempts': 1, 'latency_ms': 1548.6, 'token_usage': {'input_tokens': 260, 'output_tokens': 22, 'total_tokens': 282, 'input_token_details': {'audio': 0, 'cache_read': 0, 'cache_creation': 0}, 'output_token_details': {'audio': 0, 'reasoning': 0}}}
[답변] {'answer': 'VPN 문의 대상은 IT 지원팀입니다.', 'sources': ['it-01'], 'status': 'grounded', 'route': 'primary'}
{'session': 'b', 'status': 'not_found', 'route': 'local', 'attempts': 0, 'latency_ms': 0.3, 'token_usage': 'not_available'}
[답변] {'answer': '관련 문서를 찾지 못했습니다.', 'sources': [], 'status': 'not_found', 'route': 'local'}
{'session': 'c', 'status': 'grounded', 'route': 'primary', 'attempts': 2, 'latency_ms': 1163.6, 'token_usage': {'input_tokens': 257, 'output_tokens': 31, 'total_tokens': 288, 'input_token_details': {'audio': 0, 'cache_read': 0, 'cache_creation': 0}, 'output_token_details': {'audio': 0, 'reasoning': 0}}}
[답변] {'answer': '교육비는 팀장 승인 후 신청서를 교육 담당자에게 제출하여 신청합니다.', 'sources': ['hr-01'], 'status': 'grounded', 'route': 'primary'}
{'session': 'd', 'status': 'degraded', 'route': 'fallback', 'attempts': 2, 'latency_ms': 1.6, 'token_usage': 'not_available'}
[답변] {'answer': '현재 답변을 만들 수 없습니다. 담당 부서에 문의해 주세요.', 'sources': [], 'status': 'degraded', 'route': 'fallback'}
[확인] 세션 분리 및 검증 후 저장 완료