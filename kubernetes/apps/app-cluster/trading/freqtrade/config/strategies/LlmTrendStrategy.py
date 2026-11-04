"""Trend-following spot strategy with an LLM entry veto.

Technical rules decide every trade. Before an entry is placed in dry-run or
live mode, an LLM (via the LiteLLM gateway) sees recent daily candles and can
veto the entry. It can never open, size or close a trade. Any failure (no key,
timeout, bad reply) vetoes the entry: fail closed.

Environment:
    LLM_FILTER_ENABLED  "true" (default) or "false" to trade on rules alone
    LLM_BASE_URL        OpenAI-compatible base URL, e.g. http://litellm.krapulax.home/v1
    LLM_API_KEY         LiteLLM virtual key
    LLM_MODEL           model name exposed by LiteLLM
    LLM_CACHE_HOURS     how long a verdict per pair is reused (default 12)
    LLM_RETRY_MINUTES   how long a failed call vetoes before retrying (default 30)
    LLM_LOG_PATH        JSONL decision log (default /freqtrade/user_data/llm_decisions.jsonl)
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.enums import RunMode
from freqtrade.strategy import IStrategy, informative
from technical import qtpylib

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a cautious risk filter for a long-only crypto spot trading bot. "
    "You receive recent daily OHLCV candles for one pair and a proposed long entry "
    "from a trend-following rule. Decide whether market conditions favour taking it. "
    "Prefer 'risk_off' when the trend is unclear, volatility is extreme, or the move "
    "looks exhausted. Reply with JSON only: "
    '{"regime": "risk_on" | "neutral" | "risk_off", "confidence": 0.0-1.0, '
    '"reason": "one short sentence"}'
)


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class LlmTrendStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "4h"
    can_short = False
    startup_candle_count = 210

    minimal_roi = {"0": 0.25}
    stoploss = -0.08
    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._llm_cache: dict[str, tuple[datetime, dict]] = {}

    @property
    def protections(self):
        return [
            # Do not re-enter a pair straight after leaving it.
            {"method": "CooldownPeriod", "stop_duration_candles": 3},
            # Two stop-losses in two days: pause everything for a day.
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 12,
                "trade_limit": 2,
                "stop_duration_candles": 6,
                "only_per_pair": False,
            },
            # Account drawdown above 15% over ~2 weeks: pause for two days.
            {
                "method": "MaxDrawdown",
                "calculation_mode": "equity",
                "lookback_period_candles": 84,
                "trade_limit": 1,
                "stop_duration_candles": 12,
                "max_allowed_drawdown": 0.15,
            },
        ]

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema55"] = ta.EMA(dataframe, timeperiod=55)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe["ema21"], dataframe["ema55"])
                & (dataframe["close"] > dataframe["ema200"])
                & (dataframe["close_1d"] > dataframe["ema50_1d"])
                & (dataframe["rsi"] < 70)
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "ema_cross")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            qtpylib.crossed_below(dataframe["ema21"], dataframe["ema55"])
            & (dataframe["volume"] > 0),
            ["exit_long", "exit_tag"],
        ] = (1, "ema_cross_down")
        return dataframe

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        # Backtests and hyperopt measure the technical rules only.
        if self.dp.runmode not in (RunMode.DRY_RUN, RunMode.LIVE):
            return True
        if not _env_bool("LLM_FILTER_ENABLED", True):
            return True

        verdict = self._llm_verdict(pair, rate, current_time)
        allowed = verdict.get("ok", False) and verdict.get("regime") == "risk_on"
        logger.info(
            "LLM veto check %s: regime=%s confidence=%s allowed=%s reason=%s",
            pair,
            verdict.get("regime"),
            verdict.get("confidence"),
            allowed,
            verdict.get("reason") or verdict.get("error"),
        )
        return allowed

    def _llm_verdict(self, pair: str, rate: float, now: datetime) -> dict:
        # Freqtrade re-checks an open entry signal every few seconds, so every
        # outcome is cached: answers for LLM_CACHE_HOURS, failures for
        # LLM_RETRY_MINUTES (so a broken gateway is not hammered).
        cached = self._llm_cache.get(pair)
        if cached:
            ttl = (
                timedelta(hours=float(os.environ.get("LLM_CACHE_HOURS", "12")))
                if cached[1].get("ok")
                else timedelta(minutes=float(os.environ.get("LLM_RETRY_MINUTES", "30")))
            )
            if now - cached[0] < ttl:
                return cached[1]

        verdict = self._ask_llm(pair, rate)
        verdict["pair"] = pair
        verdict["time"] = now.astimezone(timezone.utc).isoformat()
        self._log_decision(verdict)
        self._llm_cache[pair] = (now, verdict)
        return verdict

    def _ask_llm(self, pair: str, rate: float) -> dict:
        base_url = os.environ.get("LLM_BASE_URL", "").rstrip("/")
        api_key = os.environ.get("LLM_API_KEY", "")
        model = os.environ.get("LLM_MODEL", "")
        if not (base_url and api_key and model):
            return {"ok": False, "error": "LLM_BASE_URL, LLM_API_KEY or LLM_MODEL not set"}

        daily = self.dp.get_pair_dataframe(pair=pair, timeframe="1d")
        if daily is None or len(daily) < 30:
            return {"ok": False, "error": "not enough daily candles"}
        candles = daily.tail(60)[["date", "open", "high", "low", "close", "volume"]].copy()
        candles["date"] = candles["date"].dt.strftime("%Y-%m-%d")
        rows = candles.round(6).values.tolist()

        user_msg = json.dumps(
            {
                "pair": pair,
                "proposed_action": "open long",
                "entry_price": rate,
                "rule": "4h EMA21 crossed above EMA55, price above 4h EMA200 and daily EMA50",
                "daily_candles_columns": ["date", "open", "high", "low", "close", "volume"],
                "daily_candles": rows,
            }
        )
        body = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 300,
                "temperature": 0,
            }
        ).encode()
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read())
            content = payload["choices"][0]["message"]["content"] or ""
        except Exception as exc:  # network, HTTP or schema errors all veto
            return {"ok": False, "error": f"request failed: {type(exc).__name__}: {exc}"[:300]}
        return self._parse_reply(content)

    @staticmethod
    def _parse_reply(content: str) -> dict:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return {"ok": False, "error": "no JSON in reply", "raw": content[:300]}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"ok": False, "error": "invalid JSON in reply", "raw": content[:300]}
        regime = str(data.get("regime", "")).strip().lower()
        if regime not in ("risk_on", "neutral", "risk_off"):
            return {"ok": False, "error": f"unknown regime {regime!r}", "raw": content[:300]}
        try:
            confidence = float(data.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0
        return {
            "ok": True,
            "regime": regime,
            "confidence": confidence,
            "reason": str(data.get("reason", ""))[:300],
        }

    @staticmethod
    def _log_decision(verdict: dict) -> None:
        path = os.environ.get("LLM_LOG_PATH", "/freqtrade/user_data/llm_decisions.jsonl")
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(verdict) + "\n")
        except OSError as exc:
            logger.warning("Could not write LLM decision log %s: %s", path, exc)
