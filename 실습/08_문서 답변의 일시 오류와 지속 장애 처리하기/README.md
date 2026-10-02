## 문제: 문서 답변이 실패했을 때 다음 행동 정하기

사내 문서에 답하는 Private LLM 서비스가 모델 연결 오류를 만났습니다. 한 번 더 실행하면 회복되는 경우가 있지만, 계속 실패하는 요청도 있습니다. 비어 있는 질문까지 반복하거나 장애 안내를 정상 답변처럼 보여 주면 운영 담당자와 사용자가 결과를 잘못 이해하게 됩니다.

모델 단계의 오류 정책을 완성하세요. 회복 가능한 오류에서는 최초 호출을 포함해 최대 두 번 시도하고, 두 번 모두 실패하면 담당 부서에 문의하라는 제한 안내를 반환합니다. 입력 오류는 이 정책으로 숨기지 않습니다.

정책을 확인할 때는 고정 오류 훈련을 먼저 실행합니다. 훈련은 실제 API를 호출하지 않으며, 마지막 실행만 OpenAI API로 가상의 VPN 문서 답변을 생성합니다. 두 결과는 출력 제목으로 구분됩니다.

### 공통 출력 계약

모델이 답한 경로와 제한 안내 경로 모두 제공된 Pydantic `UserAnswer` 객체를 반환합니다.

| 필드 | 정상 모델 경로 | 제한 안내 경로 |
| --- | --- | --- |
| `status` | `ok` | `degraded` |
| `route` | `primary` | `fallback` |
| `answer` | 모델이 문서를 읽고 생성한 답변 | 현재 기능 제한과 다음 행동을 알리는 고정 안내 |

제한 안내는 모델의 정상 답변을 흉내 내는 문장이 아닙니다. 상세 답변을 제공하지 못했다는 사실을 `status`와 본문에 함께 표시합니다.

### 오류별 처리 기준

제공된 `RECOVERABLE` 목록에는 다음 예외가 있습니다.

| 예외 | 이 실습의 의미 |
| --- | --- |
| `TemporaryModelError` | 코드가 계획적으로 발생시키는 훈련용 일시 오류 |
| `APIConnectionError` | 실제 API 연결 오류. SDK의 API timeout 오류도 이 계열에 포함 |
| `InternalServerError` | 실제 API 서버의 일시 장애 계열 |

`ValueError`, 응답 형식 오류, 인증 오류, 요청 제한·요금 한도 오류는 이 목록에 넣지 않습니다. 같은 입력을 반복하거나 고정 안내로 바꿔서 해결할 수 있는지 확인하지 않은 오류까지 처리하지 않기 위한 범위입니다.

### 완성할 부분

**TODO 1 — Retry 다음에 Fallback 연결하기**

`build_policy(primary, fallback)`은 두 함수를 받아 오류 정책이 적용된 Runnable을 반환합니다.

1. `primary`를 `RunnableLambda`로 감쌉니다.
2. `with_retry()`에서 대상 예외를 `RECOVERABLE`, 전체 시도를 `2`, `wait_exponential_jitter`를 `False`로 지정합니다.
3. 반환된 Retry Runnable에 `with_fallbacks()`를 연결합니다. 대체 함수도 Runnable로 감싸 목록에 넣고, `exceptions_to_handle`에 같은 예외 목록을 지정합니다.

처리 순서는 Primary → 허용한 Retry → 소진 시 Fallback입니다. 첫 Primary 호출이 성공하면 뒤의 대체 함수는 실행하지 않습니다.

**TODO 2 — 제한 안내 만들기**

`fallback_answer(_)`는 전달받은 값을 사용하지 않고 `UserAnswer`를 반환합니다. `status`는 `degraded`, `route`는 `fallback`으로 지정하세요. `answer`에는 현재 문서 답변을 만들 수 없으며 IT 지원팀에 문의해 달라는 내용을 넣습니다. 고정 안내의 표현은 바꿔도 되지만 정상 답변처럼 보이면 안 됩니다.

**TODO 3 — 고정 오류 훈련의 진입 수와 실패 조건 구현하기**

`build_drill(failures)` 안의 `primary(question)`을 완성합니다. 각 훈련은 새로운 `counts` 딕셔너리를 사용합니다.

- 함수에 진입할 때마다 `counts["primary"]`를 1 증가시킵니다. 잘못된 입력으로 실패한 진입도 셉니다.
- 질문이 문자열이 아니거나 공백뿐이면 `ValueError`를 발생시킵니다.
- 진입 수가 `failures` 이하이면 `TemporaryModelError`를 발생시킵니다.
- 두 조건을 통과하면 제공된 정상 결과 반환 코드가 실행됩니다.

입력 검사를 계획된 장애 검사보다 먼저 해야 비어 있는 질문이 일시 장애로 잘못 분류되지 않습니다.

### 제공된 실제 호출 경로

실제 실행에서는 Prompt를 먼저 만들고, `live_primary()`의 모델 호출 단계에 같은 오류 정책을 적용합니다. 질문이나 검색 결과를 저장하는 코드는 이 Retry 안에 들어 있지 않습니다. 모델 내부의 `max_retries=0`과 바깥의 최대 두 번 시도를 함께 확인하세요.

`timeout=30`은 한 요청 시도의 대기 제한을 위한 클라이언트 설정입니다. Retry 횟수를 정하는 기능과는 다릅니다. `wait_exponential_jitter=False`는 이 작은 정책 확인에서 별도의 지수 대기와 무작위 지연을 넣지 않는 설정입니다. 운영 서비스의 재시도 간격을 결정하는 완성 정책으로 사용하지 않습니다.

# 실행결과

[고정 오류 훈련:정상] ok/primary {'primary': 1, 'fallback': 0}
[고정 오류 훈련:복구] ok/primary {'primary': 2, 'fallback': 0}
[고정 오류 훈련:장애] degraded/fallback {'primary': 2, 'fallback': 1}
[고정 오류 훈련:입력 오류] ValueError {'primary': 1, 'fallback': 0}
[실제 API 경로] {'status': 'ok', 'answer': 'IT 지원팀에 문의합니다.', 'route': 'primary'}