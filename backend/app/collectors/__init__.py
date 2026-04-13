"""Data collectors for real-time market data.

Collectors fetch structured numeric data from APIs and store it in
time-series tables (price_ticks, market_metrics, onchain_metrics).
They also publish events to Redis Streams for downstream consumers.
"""
