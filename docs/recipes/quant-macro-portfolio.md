# Overnight portfolio optimization (recipe)

> **Recipe — not runnable yet.** This is an aspirational loop from the *Infinite
> Improvement Loop*; the engine does not execute it today. See its runnable
> narrow demo in the showcase.

## The loop
Quant Dev + Risk Manager personas backtest micro-strategies over live order books and macro data, auto-correct parameters, and iterate overnight until a risk-mitigated allocation survives a stress scenario.

## What it would need
A market-data feed as target, a backtest/Sharpe + drawdown scorer as the referee, and an exit criterion of 'survives a 2008-style simulated crash with Sharpe > 2.0'.

## Why it isn't runnable yet
CLI-Judge has no financial-backtest fixture suite, and the loop requires live sandboxed strategy execution we don't run. The narrow `quant-macro` demo (FX rate CLI) IS runnable; this broader optimization loop is not.
