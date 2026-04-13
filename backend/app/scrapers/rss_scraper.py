import logging
from datetime import datetime, timezone

import feedparser
import httpx

from app.scrapers.base import BaseScraper, RawItem

logger = logging.getLogger(__name__)

DEFAULT_RSS_SOURCES = [
    # =========================================================================
    # DACH REGULATORS
    # =========================================================================
    {"id": "bafin-de", "name": "BaFin Meldungen (DE)", "type": "rss", "category": "regulation", "url": "https://www.bafin.de/DE/Service/TopNavigation/RSS/_function/rssnewsfeed.xml", "frequency": 30},
    {"id": "bafin-en", "name": "BaFin Publications (EN)", "type": "rss", "category": "regulation", "url": "https://www.bafin.de/EN/Service/TopNavigation/RSS/_function/rssnewsfeed.xml", "frequency": 30},
    {"id": "finma-news", "name": "FINMA News", "type": "rss", "category": "regulation", "url": "https://www.finma.ch/en/rss/news/", "frequency": 30},
    {"id": "finma-sanctions", "name": "FINMA Sanctions", "type": "rss", "category": "regulation", "url": "https://www.finma.ch/en/rss/sanktionen/", "frequency": 60},
    {"id": "fma-austria", "name": "FMA Austria News", "type": "rss", "category": "regulation", "url": "https://www.fma.gv.at/rss/", "frequency": 60},
    # =========================================================================
    # DACH MEDIA & FINANCE
    # =========================================================================
    {"id": "btc-echo", "name": "BTC-ECHO (DE)", "type": "rss", "category": "market", "url": "https://www.btc-echo.de/feed/", "frequency": 15},
    {"id": "crypto-valley-journal", "name": "Crypto Valley Journal (CH)", "type": "rss", "category": "market", "url": "https://cryptovalleyjournal.com/feed/", "frequency": 30},
    {"id": "handelsblatt-finanzen", "name": "Handelsblatt Finanzen", "type": "rss", "category": "market", "url": "https://www.handelsblatt.com/contentexport/feed/finanzen", "frequency": 30},
    {"id": "nzz-finanzen", "name": "NZZ Finanzen", "type": "rss", "category": "market", "url": "https://www.nzz.ch/finanzen.rss", "frequency": 30},
    {"id": "der-standard-wirtschaft", "name": "Der Standard Wirtschaft (AT)", "type": "rss", "category": "market", "url": "https://www.derstandard.at/rss/wirtschaft", "frequency": 30},
    {"id": "wirtschaftswoche", "name": "WirtschaftsWoche", "type": "rss", "category": "market", "url": "https://www.wiwo.de/contentexport/feed/rss/schlagzeilen", "frequency": 30},
    {"id": "finews-ch", "name": "Finews.ch (Swiss Finance)", "type": "rss", "category": "market", "url": "https://www.finews.ch/rss-feeds", "frequency": 30},
    {"id": "swissinfo-business", "name": "SwissInfo Business", "type": "rss", "category": "market", "url": "https://www.swissinfo.ch/eng/business/rss", "frequency": 30},
    {"id": "blocktrainer-de", "name": "Blocktrainer (DE)", "type": "rss", "category": "market", "url": "https://www.blocktrainer.de/feed/", "frequency": 30},
    # =========================================================================
    # USA REGULATORS
    # =========================================================================
    {"id": "sec-press", "name": "SEC Press Releases", "type": "rss", "category": "regulation", "url": "https://www.sec.gov/rss/news/press.xml", "frequency": 60},
    {"id": "sec-litigation", "name": "SEC Litigation Releases", "type": "rss", "category": "regulation", "url": "https://www.sec.gov/rss/litigation/litreleases.xml", "frequency": 60},
    {"id": "cftc-press", "name": "CFTC Press Releases", "type": "rss", "category": "regulation", "url": "https://www.cftc.gov/PressRoom/PressReleases/rss.xml", "frequency": 60},
    {"id": "fed-press", "name": "Federal Reserve Press", "type": "rss", "category": "regulation", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "frequency": 60},
    {"id": "occ-news", "name": "OCC News Releases", "type": "rss", "category": "regulation", "url": "https://www.occ.treas.gov/news-issuances/news-releases/rss-feed.xml", "frequency": 60},
    {"id": "fdic-press", "name": "FDIC Press Releases", "type": "rss", "category": "regulation", "url": "https://www.fdic.gov/news/press-releases/index.xml", "frequency": 60},
    {"id": "treasury-press", "name": "US Treasury Press", "type": "rss", "category": "regulation", "url": "https://home.treasury.gov/system/files/136/press-releases.xml", "frequency": 60},
    # =========================================================================
    # USA CRYPTO & FINANCE MEDIA
    # =========================================================================
    {"id": "coindesk-rss", "name": "CoinDesk", "type": "rss", "category": "market", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml", "frequency": 15},
    {"id": "cointelegraph-rss", "name": "CoinTelegraph", "type": "rss", "category": "market", "url": "https://cointelegraph.com/rss", "frequency": 15},
    {"id": "theblock-rss", "name": "The Block", "type": "rss", "category": "market", "url": "https://www.theblock.co/rss.xml", "frequency": 15},
    {"id": "decrypt-rss", "name": "Decrypt", "type": "rss", "category": "market", "url": "https://decrypt.co/feed", "frequency": 15},
    {"id": "bitcoin-magazine", "name": "Bitcoin Magazine", "type": "rss", "category": "market", "url": "https://bitcoinmagazine.com/feed", "frequency": 30},
    {"id": "forbes-crypto", "name": "Forbes Crypto", "type": "rss", "category": "market", "url": "https://www.forbes.com/crypto-blockchain/feed/", "frequency": 15},
    {"id": "blockworks", "name": "Blockworks", "type": "rss", "category": "market", "url": "https://blockworks.co/feed", "frequency": 15},
    {"id": "dl-news", "name": "DL News", "type": "rss", "category": "market", "url": "https://www.dlnews.com/feed/", "frequency": 15},
    {"id": "unchained-crypto", "name": "Unchained Crypto", "type": "rss", "category": "market", "url": "https://unchainedcrypto.com/feed/", "frequency": 15},
    {"id": "the-defiant", "name": "The Defiant", "type": "rss", "category": "market", "url": "https://thedefiant.io/feed", "frequency": 15},
    {"id": "bloomberg-crypto", "name": "Bloomberg Crypto", "type": "rss", "category": "market", "url": "https://feeds.bloomberg.com/crypto/news.rss", "frequency": 15},
    {"id": "reuters-business", "name": "Reuters Business", "type": "rss", "category": "market", "url": "https://www.reutersagency.com/feed/?best-topics=business-finance", "frequency": 15},
    {"id": "yahoo-finance-crypto", "name": "Yahoo Finance Crypto", "type": "rss", "category": "market", "url": "https://finance.yahoo.com/rss/crypto", "frequency": 15},
    {"id": "wsj-markets", "name": "WSJ Markets", "type": "rss", "category": "market", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "frequency": 15},
    # =========================================================================
    # UK REGULATORS
    # =========================================================================
    {"id": "fca-news", "name": "FCA News (UK)", "type": "rss", "category": "regulation", "url": "https://www.fca.org.uk/news/rss.xml", "frequency": 60},
    {"id": "bank-of-england", "name": "Bank of England News", "type": "rss", "category": "regulation", "url": "https://www.bankofengland.co.uk/rss/news", "frequency": 60},
    # =========================================================================
    # EU REGULATORS
    # =========================================================================
    {"id": "ecb-press", "name": "ECB Press Releases", "type": "rss", "category": "regulation", "url": "https://www.ecb.europa.eu/rss/press.html", "frequency": 60},
    {"id": "esma-news", "name": "ESMA News", "type": "rss", "category": "regulation", "url": "https://www.esma.europa.eu/press-news/esma-news?field_type=rss", "frequency": 60},
    {"id": "eba-news", "name": "EBA News (EU Banking)", "type": "rss", "category": "regulation", "url": "https://www.eba.europa.eu/rss.xml", "frequency": 60},
    # =========================================================================
    # UK / EU CRYPTO MEDIA
    # =========================================================================
    {"id": "city-am-crypto", "name": "City AM Crypto", "type": "rss", "category": "market", "url": "https://www.cityam.com/crypto/feed/", "frequency": 30},
    {"id": "protos", "name": "Protos", "type": "rss", "category": "market", "url": "https://protos.com/feed/", "frequency": 30},
    {"id": "finextra", "name": "Finextra", "type": "rss", "category": "market", "url": "https://www.finextra.com/rss/headlines.aspx", "frequency": 30},
    # =========================================================================
    # JAPAN
    # =========================================================================
    {"id": "fsa-japan", "name": "FSA Japan News", "type": "rss", "category": "regulation", "url": "https://www.fsa.go.jp/en/rss/news.xml", "frequency": 60},
    {"id": "coinpost-jp", "name": "CoinPost (Japan)", "type": "rss", "category": "market", "url": "https://coinpost.jp/?feed=rss2", "frequency": 30},
    {"id": "cointelegraph-jp", "name": "CoinTelegraph Japan", "type": "rss", "category": "market", "url": "https://jp.cointelegraph.com/rss", "frequency": 30},
    {"id": "coindesk-jp", "name": "CoinDesk Japan", "type": "rss", "category": "market", "url": "https://www.coindeskjapan.com/feed/", "frequency": 30},
    # =========================================================================
    # KOREA
    # =========================================================================
    {"id": "blockmedia-kr", "name": "BlockMedia (Korea)", "type": "rss", "category": "market", "url": "https://www.blockmedia.co.kr/feed/", "frequency": 30},
    {"id": "tokenpost-kr", "name": "TokenPost (Korea)", "type": "rss", "category": "market", "url": "https://www.tokenpost.kr/rss", "frequency": 30},
    # =========================================================================
    # CHINA / HONG KONG / TAIWAN
    # =========================================================================
    {"id": "sfc-hk", "name": "SFC Hong Kong News", "type": "rss", "category": "regulation", "url": "https://www.sfc.hk/en/RSS", "frequency": 60},
    {"id": "cointelegraph-cn", "name": "CoinTelegraph Chinese", "type": "rss", "category": "market", "url": "https://cn.cointelegraph.com/rss", "frequency": 30},
    {"id": "8btc", "name": "8BTC (China)", "type": "rss", "category": "market", "url": "https://www.8btc.com/feed", "frequency": 30},
    {"id": "blockbeats", "name": "BlockBeats", "type": "rss", "category": "market", "url": "https://www.theblockbeats.info/rss", "frequency": 30},
    {"id": "scmp-business", "name": "SCMP Business (HK)", "type": "rss", "category": "market", "url": "https://www.scmp.com/rss/5/feed", "frequency": 30},
    {"id": "blocktempo-tw", "name": "BlockTempo (Taiwan)", "type": "rss", "category": "market", "url": "https://www.blocktempo.com/feed/", "frequency": 30},
    # =========================================================================
    # RUSSIA / EASTERN EUROPE
    # =========================================================================
    {"id": "bits-media-ru", "name": "Bits.media (Russia)", "type": "rss", "category": "market", "url": "https://bits.media/rss/", "frequency": 30},
    {"id": "forklog-ru", "name": "ForkLog (Russia/Ukraine)", "type": "rss", "category": "market", "url": "https://forklog.com/feed/", "frequency": 30},
    {"id": "cointelegraph-ru", "name": "CoinTelegraph Russia", "type": "rss", "category": "market", "url": "https://ru.cointelegraph.com/rss", "frequency": 30},
    # =========================================================================
    # MIDDLE EAST / AFRICA
    # =========================================================================
    {"id": "vara-dubai", "name": "VARA Dubai News", "type": "rss", "category": "regulation", "url": "https://www.vara.ae/en/news/rss", "frequency": 60},
    {"id": "arabian-business", "name": "Arabian Business", "type": "rss", "category": "market", "url": "https://www.arabianbusiness.com/rss", "frequency": 30},
    {"id": "gulf-news-business", "name": "Gulf News Business", "type": "rss", "category": "market", "url": "https://gulfnews.com/business/rss", "frequency": 30},
    {"id": "bitcoinke-africa", "name": "BitcoinKE (Africa)", "type": "rss", "category": "market", "url": "https://bitcoinke.io/feed/", "frequency": 30},
    # =========================================================================
    # LATIN AMERICA
    # =========================================================================
    {"id": "cointelegraph-br", "name": "CoinTelegraph Brazil", "type": "rss", "category": "market", "url": "https://br.cointelegraph.com/rss", "frequency": 30},
    {"id": "beincrypto-es", "name": "BeInCrypto Spanish", "type": "rss", "category": "market", "url": "https://es.beincrypto.com/feed/", "frequency": 30},
    {"id": "criptonoticias", "name": "CriptoNoticias", "type": "rss", "category": "market", "url": "https://www.criptonoticias.com/feed/", "frequency": 30},
    {"id": "cointelegraph-es", "name": "CoinTelegraph Spanish", "type": "rss", "category": "market", "url": "https://es.cointelegraph.com/rss", "frequency": 30},
    # =========================================================================
    # SINGAPORE / SOUTHEAST ASIA
    # =========================================================================
    {"id": "mas-singapore", "name": "MAS Singapore News", "type": "rss", "category": "regulation", "url": "https://www.mas.gov.sg/rss/news.xml", "frequency": 60},
    {"id": "forkast-news", "name": "Forkast News (Asia)", "type": "rss", "category": "market", "url": "https://forkast.news/feed/", "frequency": 15},
    {"id": "cointelegraph-sg", "name": "CoinTelegraph Singapore", "type": "rss", "category": "market", "url": "https://sg.cointelegraph.com/rss", "frequency": 30},
    # =========================================================================
    # INDIA
    # =========================================================================
    {"id": "rbi-india", "name": "RBI India Press", "type": "rss", "category": "regulation", "url": "https://www.rbi.org.in/scripts/RSS_Feeds.aspx", "frequency": 60},
    {"id": "economic-times-crypto", "name": "Economic Times Crypto (India)", "type": "rss", "category": "market", "url": "https://economictimes.indiatimes.com/markets/cryptocurrency/rssfeeds/82519898.cms", "frequency": 30},
    {"id": "coinswitch-blog", "name": "CoinSwitch Blog (India)", "type": "rss", "category": "market", "url": "https://coinswitch.co/blog/feed", "frequency": 30},
    # =========================================================================
    # AUSTRALIA
    # =========================================================================
    {"id": "asic-australia", "name": "ASIC Australia News", "type": "rss", "category": "regulation", "url": "https://asic.gov.au/about-asic/news-centre/rss-feeds/", "frequency": 60},
    {"id": "cointelegraph-au", "name": "CoinTelegraph Australia", "type": "rss", "category": "market", "url": "https://au.cointelegraph.com/rss", "frequency": 30},
    # =========================================================================
    # GLOBAL AGGREGATORS & CRYPTO MEDIA
    # =========================================================================
    {"id": "beincrypto", "name": "BeInCrypto", "type": "rss", "category": "market", "url": "https://beincrypto.com/feed/", "frequency": 15},
    {"id": "newsbtc", "name": "NewsBTC", "type": "rss", "category": "market", "url": "https://www.newsbtc.com/feed/", "frequency": 15},
    {"id": "cryptoslate", "name": "CryptoSlate", "type": "rss", "category": "market", "url": "https://cryptoslate.com/feed/", "frequency": 15},
    {"id": "cryptopotato", "name": "CryptoPotato", "type": "rss", "category": "market", "url": "https://cryptopotato.com/feed/", "frequency": 15},
    {"id": "ambcrypto", "name": "AMBCrypto", "type": "rss", "category": "market", "url": "https://ambcrypto.com/feed/", "frequency": 15},
    {"id": "u-today", "name": "U.Today", "type": "rss", "category": "market", "url": "https://u.today/rss", "frequency": 15},
    {"id": "bitcoinist", "name": "Bitcoinist", "type": "rss", "category": "market", "url": "https://bitcoinist.com/feed/", "frequency": 15},
    {"id": "cryptonews", "name": "CryptoNews", "type": "rss", "category": "market", "url": "https://cryptonews.com/news/feed/", "frequency": 15},
    {"id": "coinspeaker", "name": "Coinspeaker", "type": "rss", "category": "market", "url": "https://www.coinspeaker.com/feed/", "frequency": 15},
    {"id": "coingape", "name": "CoinGape", "type": "rss", "category": "market", "url": "https://coingape.com/feed/", "frequency": 15},
    {"id": "zycrypto", "name": "ZyCrypto", "type": "rss", "category": "market", "url": "https://zycrypto.com/feed/", "frequency": 15},
    {"id": "crypto-briefing", "name": "Crypto Briefing", "type": "rss", "category": "market", "url": "https://cryptobriefing.com/feed/", "frequency": 15},
    {"id": "blockonomi", "name": "Blockonomi", "type": "rss", "category": "market", "url": "https://blockonomi.com/feed/", "frequency": 30},
    {"id": "coinjournal", "name": "CoinJournal", "type": "rss", "category": "market", "url": "https://coinjournal.net/feed/", "frequency": 30},
    {"id": "crypto-daily", "name": "Crypto Daily", "type": "rss", "category": "market", "url": "https://cryptodaily.co.uk/feed", "frequency": 30},
    {"id": "nulltx", "name": "NullTX", "type": "rss", "category": "market", "url": "https://nulltx.com/feed/", "frequency": 30},
    {"id": "usethebitcoin", "name": "UseTheBitcoin", "type": "rss", "category": "market", "url": "https://usethebitcoin.com/feed/", "frequency": 30},
    {"id": "tronweekly", "name": "TronWeekly", "type": "rss", "category": "market", "url": "https://www.tronweekly.com/feed/", "frequency": 30},
    {"id": "coincodex", "name": "CoinCodex News", "type": "rss", "category": "market", "url": "https://coincodex.com/rss/", "frequency": 15},
    {"id": "cointelegraph-fr", "name": "CoinTelegraph French", "type": "rss", "category": "market", "url": "https://fr.cointelegraph.com/rss", "frequency": 30},
    {"id": "cointelegraph-it", "name": "CoinTelegraph Italian", "type": "rss", "category": "market", "url": "https://it.cointelegraph.com/rss", "frequency": 30},
    {"id": "cointelegraph-ar", "name": "CoinTelegraph Arabic", "type": "rss", "category": "market", "url": "https://ar.cointelegraph.com/rss", "frequency": 30},
    {"id": "cointelegraph-tr", "name": "CoinTelegraph Turkish", "type": "rss", "category": "market", "url": "https://tr.cointelegraph.com/rss", "frequency": 30},
    # =========================================================================
    # DEFI SPECIFIC
    # =========================================================================
    {"id": "rekt-news", "name": "Rekt News", "type": "rss", "category": "market", "url": "https://rekt.news/feed/", "frequency": 30},
    {"id": "week-in-ethereum", "name": "Week in Ethereum", "type": "rss", "category": "market", "url": "https://weekinethereumnews.com/feed/", "frequency": 60},
    {"id": "bankless", "name": "Bankless", "type": "rss", "category": "market", "url": "https://www.bankless.com/rss", "frequency": 30},
    {"id": "defi-pulse-blog", "name": "DeFi Pulse Blog", "type": "rss", "category": "market", "url": "https://www.defipulse.com/blog/rss.xml", "frequency": 60},
    {"id": "defi-llama-news", "name": "DeFi Llama News", "type": "rss", "category": "market", "url": "https://defillama.com/feed", "frequency": 30},
    # =========================================================================
    # INSTITUTIONAL / RESEARCH
    # =========================================================================
    {"id": "a16z-crypto", "name": "a16z Crypto Blog", "type": "rss", "category": "competition", "url": "https://a16zcrypto.com/feed/", "frequency": 60},
    {"id": "paradigm-blog", "name": "Paradigm Research", "type": "rss", "category": "competition", "url": "https://www.paradigm.xyz/feed.xml", "frequency": 60},
    {"id": "galaxy-digital", "name": "Galaxy Digital Research", "type": "rss", "category": "competition", "url": "https://www.galaxy.com/research/rss/", "frequency": 60},
    {"id": "grayscale-blog", "name": "Grayscale Blog", "type": "rss", "category": "competition", "url": "https://www.grayscale.com/blog/rss.xml", "frequency": 60},
    {"id": "pantera-capital", "name": "Pantera Capital Blog", "type": "rss", "category": "competition", "url": "https://panteracapital.com/feed/", "frequency": 60},
    {"id": "messari-research", "name": "Messari Research", "type": "rss", "category": "competition", "url": "https://messari.io/rss", "frequency": 60},
    {"id": "delphi-digital", "name": "Delphi Digital Blog", "type": "rss", "category": "competition", "url": "https://www.delphidigital.io/feed", "frequency": 60},
    {"id": "coinmetrics-blog", "name": "Coin Metrics Blog", "type": "rss", "category": "competition", "url": "https://coinmetrics.io/feed/", "frequency": 60},
    {"id": "chainalysis-blog", "name": "Chainalysis Blog", "type": "rss", "category": "competition", "url": "https://blog.chainalysis.com/feed/", "frequency": 60},
    {"id": "glassnode-insights", "name": "Glassnode Insights", "type": "rss", "category": "competition", "url": "https://insights.glassnode.com/rss/", "frequency": 60},
    {"id": "ethereum-foundation", "name": "Ethereum Foundation Blog", "type": "rss", "category": "competition", "url": "https://blog.ethereum.org/feed.xml", "frequency": 60},
    {"id": "binance-research", "name": "Binance Research", "type": "rss", "category": "competition", "url": "https://research.binance.com/feed", "frequency": 60},
    # =========================================================================
    # CANADIAN REGULATORS
    # =========================================================================
    {"id": "osc-canada", "name": "OSC Canada News", "type": "rss", "category": "regulation", "url": "https://www.osc.ca/en/rss.xml", "frequency": 60},
    # =========================================================================
    # On-Chain Data (non-RSS, handled by dedicated scrapers)
    # =========================================================================
    {"id": "coingecko-market", "name": "CoinGecko Market Data", "type": "coingecko", "category": "market", "url": "https://api.coingecko.com/api/v3", "frequency": 5},
    {"id": "defillama-tvl", "name": "DeFi Llama TVL", "type": "defillama", "category": "market", "url": "https://api.llama.fi", "frequency": 15},
]


class RssScraper(BaseScraper):
    source_type = "rss"

    async def scrape(self, source: dict) -> list[RawItem]:
        url = source.get("url", "")
        if not url:
            logger.warning(f"No URL for source {source.get('name')}")
            return []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return []

        feed = feedparser.parse(resp.text)
        items = []

        for entry in feed.entries[:50]:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")

            items.append(
                RawItem(
                    title=entry.get("title", "Untitled"),
                    content=content,
                    url=entry.get("link", ""),
                    author=entry.get("author", ""),
                    published_at=published,
                )
            )

        logger.info(f"RSS scraped {len(items)} items from {source.get('name')}")
        return items
