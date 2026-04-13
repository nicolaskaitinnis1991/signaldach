"""Entity extraction for crypto/DACH news items.

Extracts token names, company names, and regulator names from text
using curated keyword lists. No ML models required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class Entity:
    name: str
    entity_type: str  # "token", "company", "regulator", "person"
    normalized: str  # canonical form for deduplication


# --- Token / Cryptocurrency names ---
# Maps aliases/variations -> canonical name
TOKEN_MAP: dict[str, str] = {
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH", "ether": "ETH",
    "solana": "SOL", "sol": "SOL",
    "ripple": "XRP", "xrp": "XRP",
    "cardano": "ADA", "ada": "ADA",
    "polkadot": "DOT", "dot": "DOT",
    "avalanche": "AVAX", "avax": "AVAX",
    "chainlink": "LINK", "link": "LINK",
    "polygon": "MATIC", "matic": "MATIC",
    "litecoin": "LTC", "ltc": "LTC",
    "dogecoin": "DOGE", "doge": "DOGE",
    "shiba inu": "SHIB", "shib": "SHIB",
    "uniswap": "UNI", "uni": "UNI",
    "aave": "AAVE",
    "tether": "USDT", "usdt": "USDT",
    "usdc": "USDC", "usd coin": "USDC",
    "bnb": "BNB", "binance coin": "BNB",
    "tron": "TRX", "trx": "TRX",
    "stellar": "XLM", "xlm": "XLM",
    "cosmos": "ATOM", "atom": "ATOM",
    "near": "NEAR", "near protocol": "NEAR",
    "arbitrum": "ARB", "arb": "ARB",
    "optimism": "OP",
    "sui": "SUI",
    "aptos": "APT", "apt": "APT",
    "pepe": "PEPE",
    "stablecoin": "STABLECOIN",
    "stablecoins": "STABLECOIN",
    "cbdc": "CBDC",
    "nft": "NFT", "nfts": "NFT",
    "defi": "DEFI",
}

# --- Companies / Projects relevant to DACH crypto ---
COMPANY_MAP: dict[str, str] = {
    "21shares": "21Shares",
    "21 shares": "21Shares",
    "bitcoin suisse": "Bitcoin Suisse",
    "amina bank": "AMINA Bank",
    "amina": "AMINA Bank",
    "seba bank": "SEBA Bank",
    "seba": "SEBA Bank",
    "crypto finance": "Crypto Finance AG",
    "crypto finance ag": "Crypto Finance AG",
    "dda": "Deutsche Digital Assets",
    "deutsche digital assets": "Deutsche Digital Assets",
    "coinshares": "CoinShares",
    "bitpanda": "Bitpanda",
    "scalable capital": "Scalable Capital",
    "scalable": "Scalable Capital",
    "trade republic": "Trade Republic",
    "n26": "N26",
    "swissborg": "SwissBorg",
    "sygnum": "Sygnum Bank",
    "sygnum bank": "Sygnum Bank",
    "boerse stuttgart": "Boerse Stuttgart Digital",
    "bsdex": "BSDEX",
    "blocktrade": "Blocktrade",
    "binance": "Binance",
    "coinbase": "Coinbase",
    "kraken": "Kraken",
    "blackrock": "BlackRock",
    "grayscale": "Grayscale",
    "fidelity": "Fidelity",
    "microstrategy": "MicroStrategy",
    "strategy": "MicroStrategy",
    "tether": "Tether",
    "circle": "Circle",
    "ripple": "Ripple",
    "consensys": "ConsenSys",
    "galaxy digital": "Galaxy Digital",
    "deutsche bank": "Deutsche Bank",
    "commerzbank": "Commerzbank",
    "ubs": "UBS",
    "credit suisse": "Credit Suisse",
    "raiffeisen": "Raiffeisen",
}

# --- Regulators ---
REGULATOR_MAP: dict[str, str] = {
    "bafin": "BaFin",
    "bundesanstalt": "BaFin",
    "finma": "FINMA",
    "fma": "FMA Austria",
    "fma austria": "FMA Austria",
    "esma": "ESMA",
    "ecb": "ECB",
    "european central bank": "ECB",
    "sec": "SEC",
    "cftc": "CFTC",
    "mica": "MiCA",
    "markets in crypto-assets": "MiCA",
    "markets in crypto assets": "MiCA",
    "european commission": "European Commission",
    "european parliament": "European Parliament",
    "bundesbank": "Bundesbank",
    "snb": "SNB",
    "swiss national bank": "SNB",
    "oesterreichische nationalbank": "OeNB",
    "oenb": "OeNB",
    "fatf": "FATF",
    "financial action task force": "FATF",
    "bis": "BIS",
    "bank for international settlements": "BIS",
}

# Pre-compile a single regex for token tickers (uppercase, 2-5 chars, word boundary)
_TICKER_RE = re.compile(
    r'\b(' + '|'.join(
        re.escape(t) for t in sorted(
            set(TOKEN_MAP.values()), key=len, reverse=True
        )
        if t.isupper() and len(t) >= 2
    ) + r')\b'
)


def extract_entities(text: str) -> List[Entity]:
    """Extract all recognized entities from text.

    Returns deduplicated list of Entity objects.
    """
    if not text:
        return []

    entities: dict[str, Entity] = {}  # keyed by (type, normalized)
    text_lower = text.lower()

    # --- Tokens (check lowercase aliases first) ---
    for alias, canonical in TOKEN_MAP.items():
        if alias in text_lower:
            key = f"token:{canonical}"
            if key not in entities:
                entities[key] = Entity(
                    name=canonical, entity_type="token", normalized=canonical
                )

    # Also scan for uppercase tickers directly (handles BTC, ETH etc. in original text)
    for match in _TICKER_RE.finditer(text):
        ticker = match.group(1)
        key = f"token:{ticker}"
        if key not in entities:
            entities[key] = Entity(
                name=ticker, entity_type="token", normalized=ticker
            )

    # --- Companies ---
    for alias, canonical in COMPANY_MAP.items():
        if alias in text_lower:
            key = f"company:{canonical}"
            if key not in entities:
                entities[key] = Entity(
                    name=canonical, entity_type="company", normalized=canonical
                )

    # --- Regulators ---
    for alias, canonical in REGULATOR_MAP.items():
        if alias in text_lower:
            key = f"regulator:{canonical}"
            if key not in entities:
                entities[key] = Entity(
                    name=canonical, entity_type="regulator", normalized=canonical
                )

    return list(entities.values())


def entities_to_dict(entities: List[Entity]) -> dict:
    """Convert entity list to a JSON-serializable dict grouped by type."""
    result: dict[str, list[str]] = {
        "tokens": [],
        "companies": [],
        "regulators": [],
    }
    for e in entities:
        if e.entity_type == "token":
            result["tokens"].append(e.normalized)
        elif e.entity_type == "company":
            result["companies"].append(e.normalized)
        elif e.entity_type == "regulator":
            result["regulators"].append(e.normalized)
    return result
