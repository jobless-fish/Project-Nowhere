"""Why a model call failed, in words a person can act on (used by briefings, reply drafts and document extraction)."""
import re

_KEY_LIKE = re.compile(r"(AIza[0-9A-Za-z_\-]{10,}|sk-[A-Za-z0-9_\-]{10,}|Bearer\s+\S+)")


def explain_llm_failure(err: str) -> dict:
    """Why the model could not answer, in words a person can act on. The raw text is kept short and scrubbed of anything that looks like a key."""
    e = err or ""
    low = e.lower()
    if "429" in e or "too many requests" in low or "quota" in low:
        why = "모델 요청 한도를 넘었어요(429). 잠시 뒤 다시 하거나, 한도가 더 큰 키를 쓰세요."
    elif "401" in e or "403" in e or "unauthorized" in low or "forbidden" in low or "api key" in low:
        why = "키가 없거나 잘못됐거나 이 모델을 쓸 권한이 없어요(401/403)."
    elif "404" in e or "not found" in low:
        why = "모델 이름이나 주소가 잘못됐어요(404). LLM_MODEL과 LLM_BASE_URL을 확인하세요."
    elif "timeout" in low or "timed out" in low:
        why = "모델 응답이 너무 느려서 시간이 초과됐어요."
    elif "no json" in low or "jsondecode" in low or "expecting" in low:
        why = "모델이 약속한 JSON 형식으로 답하지 않았어요."
    elif any(c in e for c in ("500", "502", "503", "504")):
        why = "모델 서버 쪽 오류예요(5xx). 잠시 뒤 다시 하세요."
    else:
        why = "모델 호출 중 알 수 없는 오류가 났어요."
    return {"why": why, "raw": _KEY_LIKE.sub("***", e)[:200]}
