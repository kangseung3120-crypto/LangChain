## 문제 · 사내 문의를 분류하고 잘못된 출력 한 건 복구하기

Private LLM 문의 도우미가 직원의 요청을 읽고 담당자가 확인할 목록에 분류 결과를 보여 줍니다. 문장으로만 답하면 프로그램이 문의 종류와 담당자 확인 필요 여부를 다시 추출해야 합니다. 세 필드가 정해진 결과를 받도록 만들어 보겠습니다.

이번 문제에서는 같은 문의를 두 가지 경로로 확인합니다. 먼저 실제 모델에서 구조화된 결과를 받습니다. 이어서 기존 시스템에서 넘어왔다고 가정한 잘못된 JSON 한 건을 검증하고 한 번만 수정 요청합니다. 두 경로는 같은 스키마를 사용합니다.

### 주어진 문의와 오류 입력

```
VPN 접속 시 인증서 오류가 납니다. 담당자의 확인을 요청합니다.
```

위 문의는 `REQUEST`에 있습니다. `BROKEN_OUTPUT`은 아래의 고정 문자열입니다.

```json
{"category":"기타","needs_agent":false}
```

이 문자열은 복구 흐름을 확인하기 위해 제공한 입력입니다. 앞서 호출한 모델의 응답을 일부러 바꾸는 코드가 아닙니다. 실행할 때 원본을 미리 고치지 마세요.

### 분류 결과의 규칙

| 필드 | 타입과 조건 |
| --- | --- |
| `category` | `"접속"`, `"문서"`, `"계정"` 중 하나. VPN 연결 문제는 `"접속"`입니다. |
| `summary` | 한 문장 요약인 필수 문자열. 빈 문자열은 허용하지 않습니다. |
| `needs_agent` | 담당자 확인을 명시적으로 요청했으면 `True`. Python에서 객체를 만들거나 JSON을 Parser로 읽을 때 생략하면 `False`입니다. |

실제 문의는 `접속`으로 분류하고 담당자 확인 요청을 유지해야 합니다. 다만 스키마는 필드와 타입을 검사합니다. 요약 내용이나 분류의 의미가 맞는지는 출력과 원래 문의를 함께 읽어 확인해야 합니다.

### 직접 작성할 부분

**TODO 1 · `Ticket` 스키마**

위 표를 `BaseModel`, `Field`, `Literal`로 표현하세요. `summary`에는 `min_length=1`을, `needs_agent`에는 `default=False`를 사용합니다. 필드 설명도 함께 적으세요. 현재 준비된 `with_structured_output(Ticket)` 경로는 모델에 세 필드를 모두 포함하도록 요청합니다. 로컬 객체의 기본값 규칙과 구분하세요.

**TODO 2 · `try_parse(parser, raw)`**

JSON 문자열을 전달받은 Parser로 검사하세요. 성공하면 `Ticket` 객체, `OutputParserException`이 발생하면 `None`을 반환합니다. 실패한 결과에 기본 분류를 임의로 넣지 마세요. 제공된 `explain_error()`는 별도로 Pydantic을 직접 호출해 실패 위치를 짧게 보여 줍니다.

**TODO 3 · `repair_once(parser, repair_chain, request, raw)`**

`(최종 객체 또는 None, 수정 요청 횟수)`를 반환하세요. 첫 검증에 성공하면 객체와 `0`을 바로 반환합니다. 실패했을 때만 수정 체인을 한 번 실행합니다. 입력 키는 `request`, `broken_output`, `format_instructions`이며, 형식 안내는 전달받은 Parser의 `get_format_instructions()`로 만듭니다.

수정 체인이 반환하는 값은 문자열입니다. 처음과 같은 Parser로 재검증한 결과와 `1`을 반환하세요. 재검증이 실패해도 두 번째 수정 요청을 보내지 않습니다. API 연결 오류는 Parser 실패가 아니므로 이 함수에서 숨기지 않습니다.

# 실행결과

[로컬 기본값] False
[검증 실패] summary: missing
[검증 실패] category: literal_error
[검증 실패] JSON 문법 오류
[실제 구조화 출력] {'category': '접속', 'summary': 'VPN 접속 시 인증서 오류가 발생하여 담당자의 확인을 요청함', 'needs_agent': True}
[수정 요청 횟수] 1
[수정 후 검증] Ticket
[수정 결과] {'category': '접속', 'summary': 'VPN 접속 시 인증서 오류가 발생하여 담당자의 확인을 요청합니다.', 'needs_agent': True}