# 📈 Freqtrade Notes

Crypto spot trading bot, **dry-run only** (simulated £500, Kraken GBP pairs).
Design: [freqtrade-trading-bot.md](../../../../../docs/architecture/freqtrade-trading-bot.md).
Rollout and going-live checklist: [freqtrade-rollout.md](../../../../../docs/plan/freqtrade-rollout.md).

-   UI: `http://freqtrade.krapulax.home` (user `freqtrader`, password `FREQTRADE_UI_PASSWORD` in Doppler)
-   Strategy: `config/strategies/LlmTrendStrategy.py` (4h EMA trend rules; Claude Haiku via LiteLLM can only veto entries)
-   Bot config: `config/config.json`; secrets come in as `FREQTRADE__*` environment variables
-   Data (`/freqtrade/user_data` on the `freqtrade-data` Longhorn PVC, migrated from local-path on 2026-11-09): `tradesv3.dryrun.sqlite`, `llm_decisions.jsonl`

Useful commands:

```bash
kubectl -n trading logs deploy/freqtrade -f
kubectl -n trading exec deploy/freqtrade -- tail -n 20 /freqtrade/user_data/llm_decisions.jsonl
```

To change the strategy, edit the `.py` file and merge; Reloader restarts the pod. Open trades survive restarts (they are in SQLite).
