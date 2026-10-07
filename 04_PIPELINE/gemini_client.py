# -*- coding: utf-8 -*-
"""GA-3 Gemini 클라이언트 — 호출 예산·페이싱·재시도 정책을 코드로 강제한다.

예산 (ga2_auth_design.md 2-2 / 2-4, 사용자 GA-3 지시)
  정상 실행 목표 : 7 호출
  권고 상한      : 8 호출 (재시도 1회 포함)
  절대 상한      : 10 호출 — HARD_CAP. 초과 요청은 호출 전에 거부한다.

재시도 (2026-10-07 개정 — 503 과부하, 이어서 요청 Timeout 대응)
  HTTP 503             → 재시도. 1차 실패 후 **60초**, 2차 실패 후 **120초** 대기
  HTTP 429 (분당 한도)  → 같은 backoff. 서버가 준 retryDelay 가 더 길면 그쪽을 따른다
  **TRANSIENT_TIMEOUT** → 같은 backoff. 요청이 TIMEOUT(초) 안에 응답을 받지 못한 경우
                          (socket/read/connect timeout). 응답을 못 받은 것이지
                          요청이 거부된 것이 아니므로 일시적 장애로 본다
  HTTP 429 (일일 RPD)   → **재시도 금지. 즉시 중단** — 오늘은 회복되지 않는다
  그 외 모든 오류       → **재시도 금지. 즉시 Fail Closed**
  **단계당 최대 3회 시도(재시도 2회)**, 실행당 재시도 총 3회.
  재시도도 호출 1건으로 세며 HARD_CAP 10 을 넘지 못한다 (7 + 3 = 10).

모델 Fallback (2026-10-07 추가 — PRIMARY 2회 연속 transient 실패 대응)
  1 PRIMARY(Variable `GEMINI_MODEL`) 로 시도
  2 transient 실패 → **60초** 후 PRIMARY 1회 재시도
  3 또 transient 실패 → **120초** 후 **FALLBACK(Variable `GEMINI_MODEL_FALLBACK`) 1회**
  4 FALLBACK 성공 → 그대로 파이프라인 계속. 사용 사실을 Summary·QA 에 남긴다
  5 FALLBACK 도 실패 → **Fail Closed**
  **non-transient(인증·400·401·403·404·스키마 위반 등)는 fallback 하지 않는다** —
  재시도 자체가 허용되지 않으므로 모델을 바꿔 다시 쏘는 경로가 구조적으로 없다.
  Fallback Variable 이 비어 있으면 fallback 없이 PRIMARY 로만 3회 시도한다.
  호출 총량은 그대로 HARD_CAP 10 을 넘지 못한다.

단일 요청 timeout (TIMEOUT)
  **180초.** 2026-10-07 Dry Run 의 `UNEXPECTED_TimeoutError` 는 이 값이 짧아서가
  아니라 **180초 안에 응답이 오지 않아서** 난 것이다. 권고 기준(120초)보다 이미 길므로
  **임의로 더 늘리지 않는다.** 대신 위 분류·재시도로 흡수한다.

금지
  - 모델 ID 하드코딩 (Repository Variable GEMINI_MODEL / GEMINI_MODEL_FALLBACK 로만 주입)
  - API Key 를 URL 쿼리에 넣기 (x-goog-api-key 헤더로만)
  - Key 값·길이 출력
  - non-transient 오류에서 모델을 바꿔 재시도하는 것
  - 프롬프트에 수신주소·Secret·로컬경로·발송이력 투입 (설계 2-6)
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
)
TIMEOUT = 180   # 단일 요청 상한(초). 권고 120 이상 — 임의로 늘리지 않는다
HARD_CAP = 10
TARGET_CALLS = 7
RECOMMENDED_CAP = 8
MAX_RETRIES_PER_STAGE = 2
MAX_ATTEMPTS_PER_STAGE = MAX_RETRIES_PER_STAGE + 1   # = 3 (최초 1회 + 재시도 2회)
MAX_RETRIES_TOTAL = 3
# 재시도 대기 — 1차 실패 후 60초, 2차 실패 후 120초. 고정 스케줄이며 무한 대기가 없다.
BACKOFF_SECONDS = (60, 120)
MAX_BACKOFF_SECONDS = 180  # 서버 retryDelay 를 따르더라도 이 값을 넘지 않는다
PACE_SECONDS = 30          # RPM 5 준수 (설계 2-2)
MAX_PROMPT_CHARS = 120_000  # 호출당 입력 100K 토큰 상한의 보수적 환산
MODEL_RE = re.compile(r"^[A-Za-z0-9.\-]{1,64}$")

PER_MINUTE_HINTS = ("perminute", "per minute", "requests per minute", "rpm")
PER_DAY_HINTS = ("perday", "per day", "requests per day", "daily limit", "rpd")


class CallBudgetExceeded(Exception):
    pass


class GeminiFailClosed(Exception):
    """재시도하지 않고 중단해야 하는 모든 상황."""

    def __init__(self, category, detail=None):
        super().__init__(category)
        self.category = category
        self.detail = detail


class GeminiClient:
    def __init__(self, api_key=None, model=None, budget=None, pace=PACE_SECONDS):
        self.api_key = (api_key if api_key is not None
                        else os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model = (model if model is not None
                      else os.environ.get("GEMINI_MODEL", "")).strip()
        # Fallback 모델도 Variable 로만 주입한다. 비어 있으면 fallback 없이 동작한다.
        fb = os.environ.get("GEMINI_MODEL_FALLBACK", "").strip()
        self.fallback_model = fb if (fb and MODEL_RE.match(fb)) else ""
        self.model_used = ""
        self.primary_attempts = 0
        self.fallback_attempts = 0
        self.fallback_triggered = False
        env_budget = os.environ.get("AI_CALL_BUDGET", "").strip()
        if budget is None:
            budget = int(env_budget) if env_budget.isdigit() else HARD_CAP
        # 예산은 올릴 수 없다. HARD_CAP 이 천장이다.
        self.budget = max(1, min(int(budget), HARD_CAP))
        self.pace = pace
        self.calls = 0
        self.retries = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.tokens_total = 0
        self.log = []
        # Summary 표시용 — 시도 수 / 재시도 수 / 마지막 HTTP status / 마지막 category
        self.attempts = 0
        self.last_http_status = None
        self.last_category = None
        self.backoff_waits = []
        self._last_call_at = 0.0
        if not self.api_key:
            raise GeminiFailClosed("SECRET_MISSING_GEMINI_API_KEY")
        if not self.model or not MODEL_RE.match(self.model):
            raise GeminiFailClosed("MODEL_ID_INVALID")

    # ── 내부 ─────────────────────────────────────────────────────
    def _sanitize(self, raw):
        return C.sanitize(raw, secrets=(self.api_key,))

    def _classify(self, status, text):
        low = (text or "").lower()
        if status == 429:
            if any(h in low for h in PER_DAY_HINTS):
                return "QUOTA_EXCEEDED_PER_DAY"
            if any(h in low for h in PER_MINUTE_HINTS):
                return "QUOTA_EXCEEDED_PER_MINUTE"
            # 분당·일일을 구분할 수 없으면 보수적으로 일일로 본다 (재시도하지 않는다).
            return "QUOTA_EXCEEDED_UNKNOWN"
        if status == 503:
            return "SERVICE_UNAVAILABLE_503"
        if status == 400 and "api key not valid" in low:
            return "API_KEY_INVALID"
        if status in (401, 403):
            return "AUTH_FORBIDDEN"
        if status == 404:
            return "MODEL_NOT_FOUND"
        if status and 500 <= status < 600:
            return "SERVER_ERROR_%d" % status
        if status == 400:
            return "BAD_REQUEST_400"
        return "HTTP_%s" % status

    @staticmethod
    def _retryable(category):
        return category in ("SERVICE_UNAVAILABLE_503", "QUOTA_EXCEEDED_PER_MINUTE",
                            "TRANSIENT_TIMEOUT")

    @staticmethod
    def _retry_delay(text):
        """서버가 준 retryDelay (없으면 0). 상한을 넘기지 않는다."""
        m = re.search(r'"retryDelay"\s*:\s*"(\d+)s"', text or "")
        if m:
            return min(int(m.group(1)) + 2, MAX_BACKOFF_SECONDS)
        return 0

    @classmethod
    def backoff_for(cls, retry_index, category=None, detail=None):
        """재시도 대기 초. 1차 실패 후 60초, 2차 실패 후 120초 (고정 스케줄).

        429 에서 서버가 더 긴 retryDelay 를 주면 그쪽을 따른다 (상한 180초).
        """
        base = BACKOFF_SECONDS[min(retry_index, len(BACKOFF_SECONDS) - 1)]
        if category == "QUOTA_EXCEEDED_PER_MINUTE":
            base = max(base, cls._retry_delay(detail))
        return min(base, MAX_BACKOFF_SECONDS)

    def _model_for_attempt(self, attempt):
        """이 시도에 쓸 (모델, fallback여부). **마지막 시도만** FALLBACK 으로 간다.

        모델을 고르는 유일한 지점이다. transient 실패로 재시도가 허용된 경우에만
        이 함수가 다시 불리므로, non-transient 오류에서는 FALLBACK 경로가 없다.
        """
        if attempt >= MAX_RETRIES_PER_STAGE and self.fallback_model:
            return self.fallback_model, True
        return self.model, False

    def _reserve(self, stage):
        if self.calls + 1 > self.budget:
            raise CallBudgetExceeded(
                "AI_CALL_BUDGET 초과 — budget=%d, 요청 단계=%s" % (self.budget, stage)
            )

    def _pace_wait(self):
        if self._last_call_at:
            wait = self.pace - (time.time() - self._last_call_at)
            if wait > 0:
                print("   RPM 페이싱: %.0fs 대기" % wait, flush=True)
                time.sleep(wait)

    def _post(self, payload, model=None):
        """유일한 API 호출 지점. 재시도 루프를 이 안에 두지 않는다."""
        req = urllib.request.Request(
            ENDPOINT % (model or self.model),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        req.add_header("x-goog-api-key", self.api_key)  # URL 쿼리에 넣지 않는다
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.getcode(), resp.read().decode("utf-8", "replace")

    def _call_once(self, stage, payload, model=None):
        model = model or self.model
        self._reserve(stage)
        self._pace_wait()
        self.calls += 1
        self.attempts += 1
        if model == self.model:
            self.primary_attempts += 1
        else:
            self.fallback_attempts += 1
            self.fallback_triggered = True
        self._last_call_at = time.time()
        try:
            status, raw = self._post(payload, model)
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                body = ""
            self.last_http_status = e.code
            category = self._classify(e.code, body)
            self.last_category = category
            raise GeminiFailClosed(category, self._sanitize(body))
        except TimeoutError as e:
            # socket.timeout 은 3.10+ 에서 TimeoutError 와 같은 예외다.
            # 응답을 못 받은 것이지 요청이 거부된 것이 아니다 → 일시적 장애로 본다.
            self.last_http_status = None
            self.last_category = "TRANSIENT_TIMEOUT"
            raise GeminiFailClosed(
                "TRANSIENT_TIMEOUT",
                "request timed out after %ds (%s)" % (TIMEOUT, type(e).__name__),
            )
        except urllib.error.URLError as e:
            self.last_http_status = None
            reason = getattr(e, "reason", "")
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                self.last_category = "TRANSIENT_TIMEOUT"
                raise GeminiFailClosed(
                    "TRANSIENT_TIMEOUT",
                    "connection timed out after %ds" % TIMEOUT,
                )
            self.last_category = "NETWORK_ERROR"
            raise GeminiFailClosed("NETWORK_ERROR", self._sanitize(reason))
        except Exception as e:
            self.last_category = "UNEXPECTED_" + type(e).__name__
            raise GeminiFailClosed(self.last_category)
        self.last_http_status = status
        if status != 200:
            self.last_category = self._classify(status, raw)
            raise GeminiFailClosed(self.last_category, self._sanitize(raw))
        self.last_category = None
        self.model_used = model
        return raw

    def _parse(self, stage, raw):
        try:
            body = json.loads(raw)
        except Exception:
            self.last_category = "RESPONSE_NOT_JSON"
            raise GeminiFailClosed("RESPONSE_NOT_JSON")
        usage = body.get("usageMetadata") or {}
        self.tokens_in += int(usage.get("promptTokenCount") or 0)
        self.tokens_out += int(usage.get("candidatesTokenCount") or 0)
        self.tokens_total += int(usage.get("totalTokenCount") or 0)
        cands = body.get("candidates") or []
        if not cands:
            raise GeminiFailClosed("NO_CANDIDATES")
        finish = (cands[0].get("finishReason") or "").upper()
        if finish and finish not in ("STOP", "MAX_TOKENS"):
            # SAFETY 등 — 내용을 지어내지 않는다.
            raise GeminiFailClosed("FINISH_REASON_" + finish)
        parts = (cands[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if not text.strip():
            raise GeminiFailClosed("EMPTY_TEXT")
        try:
            return json.loads(text)
        except Exception:
            raise GeminiFailClosed("STRUCTURED_OUTPUT_PARSE_FAILED")

    # ── 공개 API ─────────────────────────────────────────────────
    def generate(self, stage, instruction, data, schema, max_output_tokens=8192):
        """구조화 출력 1단계를 수행한다.

        재시도는 503 / 429(분당) / TRANSIENT_TIMEOUT 에서만, 단계당 최대 2회
        (= 총 3회 시도)다. 대기는 60초 -> 120초 고정 스케줄이다.
        **마지막 시도는 FALLBACK 모델로 간다**(설정되어 있을 때).
        그 밖의 오류는 모델을 바꾸지 않고 즉시 Fail Closed.
        """
        prompt = instruction.strip() + "\n\n[DATA]\n" + data
        truncated = len(prompt) > MAX_PROMPT_CHARS
        if truncated:
            prompt = prompt[:MAX_PROMPT_CHARS]
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
                "maxOutputTokens": max_output_tokens,
                "temperature": 0.2,
            },
        }
        # 시도 횟수는 구조적으로 MAX_ATTEMPTS_PER_STAGE(=3)로 고정된다.
        # 무한 루프·대기 루프를 만들지 않는다 (설계 2-5 금지사항 4).
        for attempt in range(MAX_ATTEMPTS_PER_STAGE):
            # 마지막 시도(= PRIMARY 가 두 번 transient 실패한 뒤)만 FALLBACK 으로 간다.
            model, use_fallback = self._model_for_attempt(attempt)
            try:
                if use_fallback:
                    print("   FALLBACK 모델로 1회 전환 (PRIMARY transient 2회 실패)",
                          flush=True)
                raw = self._call_once(stage, payload, model)
                out = self._parse(stage, raw)
                self.log.append({
                    "stage": stage, "result": "OK", "attempt": attempt + 1,
                    "model": model, "fallback": use_fallback,
                    "calls_so_far": self.calls, "prompt_chars": len(prompt),
                    "truncated": truncated,
                })
                return out
            except GeminiFailClosed as e:
                can_retry = (
                    self._retryable(e.category)
                    and attempt < MAX_RETRIES_PER_STAGE
                    and self.retries < MAX_RETRIES_TOTAL
                    and self.calls + 1 <= self.budget
                )
                self.log.append({
                    "stage": stage, "result": "FAIL", "attempt": attempt + 1,
                    "model": model, "fallback": use_fallback,
                    "category": e.category, "detail": e.detail,
                    "http_status": self.last_http_status,
                    "calls_so_far": self.calls, "retry": bool(can_retry),
                })
                if not can_retry:
                    raise
                self.retries += 1
                delay = self.backoff_for(attempt, e.category, e.detail)
                self.backoff_waits.append(delay)
                next_model, _next_fb = self._model_for_attempt(attempt + 1)
                print("   재시도 %d/%d (%s, HTTP %s) — %ds 대기 후 `%s`"
                      % (attempt + 1, MAX_RETRIES_PER_STAGE, e.category,
                         self.last_http_status, delay, next_model), flush=True)
                time.sleep(delay)
        raise GeminiFailClosed("RETRY_EXHAUSTED_" + stage)

    def usage(self):
        return {
            "model": self.model,
            "primary_model": self.model,
            "fallback_model": self.fallback_model or "(미설정)",
            "fallback_available": bool(self.fallback_model),
            "model_used": self.model_used or "(응답 없음)",
            "primary_attempts": self.primary_attempts,
            "fallback_attempts": self.fallback_attempts,
            "fallback_triggered": self.fallback_triggered,
            "calls": self.calls,
            "attempts": self.attempts,
            "retries": self.retries,
            "last_http_status": self.last_http_status,
            "final_category": self.last_category,
            "timeout_seconds": TIMEOUT,
            "backoff_waits": self.backoff_waits,
            "max_attempts_per_stage": MAX_ATTEMPTS_PER_STAGE,
            "backoff_schedule": list(BACKOFF_SECONDS),
            "budget": self.budget,
            "hard_cap": HARD_CAP,
            "target_calls": TARGET_CALLS,
            "recommended_cap": RECOMMENDED_CAP,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "tokens_total": self.tokens_total,
            "fallback_model_used": self.fallback_triggered,
            "log": self.log,
        }
