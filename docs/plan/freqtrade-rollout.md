# 📈 Freqtrade rollout

Design: [architecture/freqtrade-trading-bot.md](../architecture/freqtrade-trading-bot.md).

## 📌 Phase 1: dry-run (this change)

### Before merge: secrets

-   [ ] In LiteLLM (`https://litellm.krapulax.dev/ui` → Virtual Keys → Create): key alias `freqtrade`, allowed model `openrouter/claude-haiku-5.5` only, **max budget $2**, budget duration `30d`.
-   [ ] Add these keys to Doppler `home-dc-kubernetes` / `apps`:

| Doppler key             | Value                                                                             |
| ----------------------- | --------------------------------------------------------------------------------- |
| `FREQTRADE_UI_PASSWORD` | Password for the FreqUI login (user `freqtrader`)                                 |
| `FREQTRADE_JWT_SECRET`  | Random string, e.g. `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `FREQTRADE_WS_TOKEN`    | Another random string, same command                                               |
| `FREQTRADE_LLM_API_KEY` | The LiteLLM virtual key created above (`sk-...`)                                  |

### After merge

-   [ ] Argo apps `freqtrade` (app cluster) and `litellm` (infra cluster) are `Synced/Healthy`.
-   [ ] `kubectl -n trading logs deploy/freqtrade | grep -i "dry run"` shows dry-run enabled.
-   [ ] LiteLLM is reachable from the pod (architecture doc, validation step 5).
-   [ ] Log in at `http://freqtrade.krapulax.home` (user `freqtrader`). In FreqUI: Settings → add bot → URL `http://freqtrade.krapulax.home`.
-   [ ] Run the first backup: `kubectl create job --from=cronjob/protect-freqtrade freqtrade-first -n trading`, then `task backups:run CLUSTER=app-cluster PLAN=app-freqtrade`.

### Watch it for 4–8 weeks

-   Expect **long quiet periods**. A 4h trend strategy may make only a few trades a month.
-   Weekly: FreqUI → Dashboard (profit, drawdown), Trade history, and `llm_decisions.jsonl` (what the LLM said and why).
-   Note BTC/GBP's price on the start date. The benchmark is "would I have done better just holding BTC?".

## 🔬 Phase 1b: backtest the technical baseline (optional, run locally)

The cluster pod is not a good place for this. Kraken backtest data needs trade-level downloads that are slow and RAM-heavy.

```bash
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:2026.10 \
  download-data --exchange kraken --dl-trades -p BTC/GBP ETH/GBP SOL/GBP -t 4h 1d --timerange 20250101-
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:2026.10 \
  backtesting --config user_data/config.json --strategy LlmTrendStrategy --timerange 20250101-
```

The LLM veto is skipped in backtests, so this measures the EMA/RSI rules alone.

## 💷 Phase 2: live (separate PR, not before phase 1 has run 4+ weeks)

Go/no-go: phase 1 ran 4+ weeks without errors, drawdown stayed within limits, and you accept that the money can be lost.

-   [ ] Open and verify a Kraken account; deposit a capped amount in GBP (Faster Payments).
-   [ ] Kraken → Settings → API → new key: permissions **Query funds, Query open orders & trades, Query closed orders & trades, Create & modify orders, Cancel/close orders**. **Do not tick Withdraw funds.** Restrict to the home WAN IP.
-   [ ] Doppler: add `FREQTRADE_EXCHANGE_KEY`, `FREQTRADE_EXCHANGE_SECRET`; add them to `doppler-secret.yaml` and the inventory.
-   [ ] PR: `dry_run: false`, remove `dry_run_wallet`, add `FREQTRADE__EXCHANGE__KEY/SECRET` env mapping, enable `stoploss_on_exchange`, change the DB URL to `tradesv3.live.sqlite`.
-   [ ] Optional: Telegram notifications (`FREQTRADE__TELEGRAM__TOKEN`, `..._CHAT_ID`).
-   [ ] Tax: keep the Freqtrade trade export; crypto disposals are subject to UK capital gains tax.

## 🔙 Rollback

-   Phase 1: remove the Argo app file; Argo prunes the workload; the PVC is retained.
-   Phase 2 emergency stop: FreqUI → **Stop** (no new trades) or **Force exit all**, then revert to `dry_run: true`. Revoke the Kraken API key on Kraken if in doubt.
