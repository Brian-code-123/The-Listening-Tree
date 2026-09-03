"""HK Public Holidays dataset, curated HK Local Guide dataset, and the
NewsAPI proxy with an in-memory cache — all the mostly-static HK-specific
content this app serves.
"""
import logging
import os
import time
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HK Public Holidays 2025-2027
#
# Static dataset consumed by FullCalendar on the client side.
# ---------------------------------------------------------------------------
HK_HOLIDAYS = [
    # 2025
    {"date": "2025-01-01", "name_en": "New Year's Day", "name_zh": "元旦"},
    {"date": "2025-01-29", "name_en": "Lunar New Year's Day", "name_zh": "農曆年初一"},
    {"date": "2025-01-30", "name_en": "Second day of Lunar New Year", "name_zh": "農曆年初二"},
    {"date": "2025-01-31", "name_en": "Third day of Lunar New Year", "name_zh": "農曆年初三"},
    {"date": "2025-04-04", "name_en": "Ching Ming Festival", "name_zh": "清明節"},
    {"date": "2025-04-18", "name_en": "Good Friday", "name_zh": "耶穌受難節"},
    {"date": "2025-04-19", "name_en": "Day after Good Friday", "name_zh": "耶穌受難節翌日"},
    {"date": "2025-04-21", "name_en": "Easter Monday", "name_zh": "復活節星期一"},
    {"date": "2025-05-01", "name_en": "Labour Day", "name_zh": "勞動節"},
    {"date": "2025-05-05", "name_en": "Buddha's Birthday", "name_zh": "佛誕"},
    {"date": "2025-05-31", "name_en": "Tuen Ng Festival", "name_zh": "端午節"},
    {"date": "2025-07-01", "name_en": "HKSAR Establishment Day", "name_zh": "香港特別行政區成立紀念日"},
    {"date": "2025-10-01", "name_en": "National Day", "name_zh": "國慶日"},
    {"date": "2025-10-07", "name_en": "Day after Mid-Autumn Festival", "name_zh": "中秋節翌日"},
    {"date": "2025-10-29", "name_en": "Chung Yeung Festival", "name_zh": "重陽節"},
    {"date": "2025-12-25", "name_en": "Christmas Day", "name_zh": "聖誕節"},
    {"date": "2025-12-26", "name_en": "Day after Christmas", "name_zh": "聖誕節後第一個周日"},
    # 2026
    {"date": "2026-01-01", "name_en": "New Year's Day", "name_zh": "元旦"},
    {"date": "2026-02-17", "name_en": "Lunar New Year's Day", "name_zh": "農曆年初一"},
    {"date": "2026-02-18", "name_en": "Second day of Lunar New Year", "name_zh": "農曆年初二"},
    {"date": "2026-02-19", "name_en": "Third day of Lunar New Year", "name_zh": "農曆年初三"},
    {"date": "2026-04-03", "name_en": "Good Friday", "name_zh": "耶穌受難節"},
    {"date": "2026-04-04", "name_en": "Day after Good Friday", "name_zh": "耶穌受難節翌日"},
    {"date": "2026-04-05", "name_en": "Ching Ming Festival", "name_zh": "清明節"},
    {"date": "2026-04-06", "name_en": "Easter Monday", "name_zh": "復活節星期一"},
    {"date": "2026-05-01", "name_en": "Labour Day", "name_zh": "勞動節"},
    {"date": "2026-05-24", "name_en": "Buddha's Birthday", "name_zh": "佛誕"},
    {"date": "2026-06-19", "name_en": "Tuen Ng Festival", "name_zh": "端午節"},
    {"date": "2026-07-01", "name_en": "HKSAR Establishment Day", "name_zh": "香港特別行政區成立紀念日"},
    {"date": "2026-09-26", "name_en": "Day after Mid-Autumn Festival", "name_zh": "中秋節翌日"},
    {"date": "2026-10-01", "name_en": "National Day", "name_zh": "國慶日"},
    {"date": "2026-10-17", "name_en": "Chung Yeung Festival", "name_zh": "重陽節"},
    {"date": "2026-12-25", "name_en": "Christmas Day", "name_zh": "聖誕節"},
    {"date": "2026-12-26", "name_en": "Day after Christmas", "name_zh": "聖誕節後第一個周日"},
    # 2027
    {"date": "2027-01-01", "name_en": "New Year's Day", "name_zh": "元旦"},
    {"date": "2027-02-06", "name_en": "Lunar New Year's Day", "name_zh": "農曆年初一"},
    {"date": "2027-02-07", "name_en": "Second day of Lunar New Year", "name_zh": "農曆年初二"},
    {"date": "2027-02-08", "name_en": "Third day of Lunar New Year", "name_zh": "農曆年初三"},
    {"date": "2027-03-26", "name_en": "Good Friday", "name_zh": "耶穌受難節"},
    {"date": "2027-03-27", "name_en": "Day after Good Friday", "name_zh": "耶穌受難節翌日"},
    {"date": "2027-03-29", "name_en": "Easter Monday", "name_zh": "復活節星期一"},
    {"date": "2027-04-05", "name_en": "Ching Ming Festival", "name_zh": "清明節"},
    {"date": "2027-05-01", "name_en": "Labour Day", "name_zh": "勞動節"},
    {"date": "2027-05-13", "name_en": "Buddha's Birthday", "name_zh": "佛誕"},
    {"date": "2027-06-09", "name_en": "Tuen Ng Festival", "name_zh": "端午節"},
    {"date": "2027-07-01", "name_en": "HKSAR Establishment Day", "name_zh": "香港特別行政區成立紀念日"},
    {"date": "2027-09-16", "name_en": "Day after Mid-Autumn Festival", "name_zh": "中秋節翌日"},
    {"date": "2027-10-01", "name_en": "National Day", "name_zh": "國慶日"},
    {"date": "2027-10-08", "name_en": "Chung Yeung Festival", "name_zh": "重陽節"},
    {"date": "2027-12-25", "name_en": "Christmas Day", "name_zh": "聖誕節"},
    {"date": "2027-12-27", "name_en": "Day after Christmas", "name_zh": "聖誕節後第一個周日"},
]

# ---------------------------------------------------------------------------
# HK News — proxy endpoint (NewsAPI with in-memory cache)
#
# Falls back to hardcoded placeholder articles when no API key is set.
# Cache TTL: 30 minutes.
# ---------------------------------------------------------------------------
NEWS_API_KEY = os.environ.get('NEWS_API_KEY', '')
_news_cache = {"data": None, "timestamp": 0, "lang": None}

async def fetch_hk_news(lang: str = 'en'):
    """Fetch HK news from NewsAPI; cache for 30 min."""
    import time
    now = time.time()
    if _news_cache["data"] and (now - _news_cache["timestamp"]) < 1800 and _news_cache["lang"] == lang:
        return _news_cache["data"]

    articles = []

    # Try NewsAPI if key available
    if NEWS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://newsapi.org/v2/top-headlines",
                    params={"country": "hk", "pageSize": 8, "apiKey": NEWS_API_KEY}
                )
                resp.raise_for_status()
                data = resp.json()
                for a in data.get("articles", [])[:8]:
                    articles.append({
                        "title": a.get("title", ""),
                        "description": a.get("description", "") or "",
                        "url": a.get("url", "#"),
                        "source": a.get("source", {}).get("name", ""),
                        "publishedAt": a.get("publishedAt", ""),
                        "image": a.get("urlToImage", ""),
                    })
        except Exception as e:
            logger.error(f"[News] NewsAPI error: {e}")

    # Fallback: use hardcoded recent HK news placeholders
    if not articles:
        if lang == 'zh-HK':
            articles = [
                {"title": "天文台預測未來數日天氣回暖", "description": "天文台表示，受暖濕氣流影響，未來數日氣溫將回升至22-25度，市民外出請注意添減衣物。", "url": "#", "source": "天文台", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "港鐵新線路規劃公佈", "description": "政府今日公佈港鐵新線路規劃詳情，包括北環線及其延伸段，預計2030年完工通車。", "url": "#", "source": "政府新聞處", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "長者醫療券使用範圍擴大", "description": "政府宣佈長者醫療券使用範圍將進一步擴大，涵蓋更多醫療服務項目，惠及更多長者。", "url": "#", "source": "衛生署", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "沙田區社區活動日即將舉行", "description": "沙田區議會將於下週末舉辦社區活動日，設有健康檢查、興趣班及長者關懷活動。", "url": "#", "source": "區議會", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "本港今日天氣晴朗乾燥", "description": "天文台錄得今日最高氣溫23度，天氣晴朗乾燥，適合戶外活動。", "url": "#", "source": "天文台", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
            ]
        else:
            articles = [
                {"title": "HK Observatory forecasts warmer weather ahead", "description": "The Observatory expects temperatures to rise to 22-25°C over the next few days due to warm moist airflow.", "url": "#", "source": "HK Observatory", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "MTR new rail line planning announced", "description": "The government today released details of new MTR rail line planning, including the Northern Link and extensions, expected to be completed by 2030.", "url": "#", "source": "GovHK", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "Elderly healthcare voucher scope expanded", "description": "The government announced an expansion of the elderly healthcare voucher scheme to cover more medical services.", "url": "#", "source": "Dept of Health", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "Sha Tin community event day coming up", "description": "The Sha Tin District Council will host a community event day next weekend featuring health checks and elderly care activities.", "url": "#", "source": "District Council", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "Fine and dry weather in Hong Kong today", "description": "The Observatory recorded a high of 23°C today. Fine and dry weather, suitable for outdoor activities.", "url": "#", "source": "HK Observatory", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
            ]

    _news_cache["data"] = articles
    _news_cache["timestamp"] = now
    _news_cache["lang"] = lang
    return articles

# ---------------------------------------------------------------------------
# HK Local Guide — Food, Shopping, Entertainment, Events
#
# Curated dataset of elderly-friendly HK local attractions with live
# refresh capability.  Data is cached for 30 minutes and can be force-
# refreshed from the client.  Each item has bilingual content.
# ---------------------------------------------------------------------------
_hk_guide_cache: dict = {"data": None, "timestamp": 0, "lang": None}

# Curated HK local guide data (bilingual)
HK_GUIDE_DATA = {
    "en": [
        # ---- FOOD ----
        {
            "category": "food",
            "name": "Tim Ho Wan — Dim Sum",
            "short_desc": "World's cheapest Michelin-star dim sum. Famous for baked BBQ pork buns.",
            "full_desc": "Tim Ho Wan is the most affordable Michelin-starred restaurant in the world. Known for their signature baked BBQ pork buns with a crispy, sweet top crust. The dim sum menu is extensive and everything is freshly made. Perfect for a casual, affordable fine-dining experience. Multiple branches across Hong Kong.",
            "location": "Sham Shui Po, Mong Kok, Central (multiple branches)",
            "price_range": "HK$50–150 per person",
            "hours": "10:00 AM – 9:30 PM daily",
            "transport": "MTR Sham Shui Po Station Exit B2 (original branch)",
            "elderly_friendly": True,
            "tips": ["Go early to avoid long queues", "Try the baked BBQ pork buns — their signature dish", "Most branches have elevator access"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Mak's Noodle — Wonton Noodles",
            "short_desc": "Legendary wonton noodles since 1920s. Thin, springy noodles with shrimp wontons.",
            "full_desc": "A Hong Kong institution for nearly 100 years, Mak's Noodle serves some of the best wonton noodles in the city. The hand-pulled noodles are thin and springy, served in a clear shrimp broth with plump shrimp wontons. Simple, affordable, and deeply satisfying.",
            "location": "Wellington Street, Central",
            "price_range": "HK$40–80 per person",
            "hours": "11:00 AM – 8:00 PM daily",
            "transport": "MTR Central Station Exit D2, 5 min walk",
            "elderly_friendly": True,
            "tips": ["Small portions — perfect for trying multiple dishes", "Cash preferred at some branches", "Air-conditioned seating available"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Tai Cheong Bakery — Egg Tarts",
            "short_desc": "Hong Kong's most famous egg tarts. Flaky crust, silky custard filling.",
            "full_desc": "Tai Cheong Bakery has been making egg tarts since 1954. The last British Governor Chris Patten was a loyal customer, earning them the nickname 'Governor's egg tarts'. The pastry has a perfectly flaky crust with smooth, lightly sweet egg custard. A must-try Hong Kong classic.",
            "location": "Lyndhurst Terrace, Central (original); multiple branches",
            "price_range": "HK$10–15 per tart",
            "hours": "7:30 AM – 9:00 PM daily",
            "transport": "MTR Central Station Exit D2",
            "elderly_friendly": True,
            "tips": ["Best eaten warm — ask for freshly baked ones", "Try the egg tarts with a cup of milk tea", "The Central branch is most iconic"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Australia Dairy Company",
            "short_desc": "Legendary cha chaan teng for scrambled eggs and milk pudding.",
            "full_desc": "This 1970s-style cha chaan teng (Hong Kong-style diner) is famous for their impossibly fluffy scrambled eggs on toast and silky steamed milk pudding. The service is famously fast and no-nonsense. Expect to share tables. A quintessential Hong Kong breakfast experience.",
            "location": "Jordan, Kowloon",
            "price_range": "HK$30–60 per person",
            "hours": "7:30 AM – 11:00 PM (closed Thursdays)",
            "transport": "MTR Jordan Station Exit C2",
            "elderly_friendly": True,
            "tips": ["Decide your order before sitting — service is lightning fast", "Must try: scrambled egg toast + milk tea", "Expect shared seating"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Lei Yue Mun Seafood Village",
            "short_desc": "Pick-your-own live seafood village by the harbour. Fresh & affordable.",
            "full_desc": "Lei Yue Mun is a fishing village turned seafood haven where you can pick live seafood from market stalls and have nearby restaurants cook it for you. Enjoy the harbour views while dining on ultra-fresh fish, prawns, lobster, and crabs. A wonderful half-day outing combining market shopping and dining.",
            "location": "Lei Yue Mun, Kwun Tong, Kowloon",
            "price_range": "HK$150–400 per person",
            "hours": "11:00 AM – 10:00 PM daily",
            "transport": "MTR Yau Tong Station Exit A2, then minibus 24",
            "elderly_friendly": True,
            "tips": ["Compare prices at different stalls", "Cooking fee is separate from seafood cost", "Beautiful sunset views from the waterfront"],
            "url": "#"
        },
        # ---- SHOPPING ----
        {
            "category": "shopping",
            "name": "Ladies' Market — Tung Choi Street",
            "short_desc": "Bustling street market with bargains on clothing, accessories, souvenirs.",
            "full_desc": "Ladies' Market on Tung Choi Street stretches over a kilometre with hundreds of stalls selling affordable clothing, bags, accessories, phone cases, souvenirs, and everyday items. Despite the name, there's plenty for everyone. A lively, colourful market experience in the heart of Mong Kok.",
            "location": "Tung Choi Street, Mong Kok",
            "price_range": "HK$10–200 per item",
            "hours": "12:00 PM – 11:30 PM daily",
            "transport": "MTR Mong Kok Station Exit D3",
            "elderly_friendly": True,
            "tips": ["Bargaining is expected — start at 50% of asking price", "Best selection in the afternoon", "Watch for pickpockets in crowded areas"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "Stanley Market",
            "short_desc": "Seaside market village with art, clothing, and waterfront restaurants.",
            "full_desc": "Stanley Market is a charming seaside market on the southern side of Hong Kong Island. Browse stalls selling art, silk garments, Chinese antiques, casual wear, and souvenirs. After shopping, enjoy seafood at the waterfront restaurants along Stanley Main Street. A relaxing half-day trip away from the city bustle.",
            "location": "Stanley, Hong Kong Island South",
            "price_range": "Varies widely",
            "hours": "10:00 AM – 6:00 PM daily",
            "transport": "Bus 6, 6X, 260 from Central (Exchange Square)",
            "elderly_friendly": True,
            "tips": ["Combine with a visit to Stanley Beach", "Waterfront restaurants have great views", "Less crowded on weekdays"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "Jade Market — Yau Ma Tei",
            "short_desc": "Traditional jade jewellery market with hundreds of stalls of Chinese jade.",
            "full_desc": "The Jade Market in Yau Ma Tei has over 400 stalls selling jade jewellery, ornaments, and carvings. Jade holds deep cultural significance in Chinese tradition, symbolizing luck, health, and longevity. Whether you're looking for a small pendant or an elaborate jade bangle, this is the place. Adjacent to the equally fascinating Temple Street Night Market.",
            "location": "Kansu Street, Yau Ma Tei",
            "price_range": "HK$50–5,000+",
            "hours": "10:00 AM – 5:00 PM daily",
            "transport": "MTR Yau Ma Tei Station Exit C",
            "elderly_friendly": True,
            "tips": ["Bring cash for better deals", "Ask for certificates for expensive pieces", "Visit Temple Street Night Market nearby in the evening"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "Sham Shui Po Fabric & Electronics",
            "short_desc": "Budget paradise for fabrics, electronics, and vintage finds.",
            "full_desc": "Sham Shui Po is Hong Kong's most authentic working-class neighbourhood. It's a treasure trove for affordable fabrics, sewing supplies, beading materials, and budget electronics. Golden Computer Arcade and nearby shops sell electronics at rock-bottom prices. The area also has some of HK's best street food.",
            "location": "Sham Shui Po, Kowloon",
            "price_range": "Very affordable",
            "hours": "10:00 AM – 8:00 PM daily",
            "transport": "MTR Sham Shui Po Station Exit D2",
            "elderly_friendly": True,
            "tips": ["Check out the fabric shops on Ki Lung Street", "Try the street food on Kweilin Street", "Golden Computer Arcade for tech bargains"],
            "url": "#"
        },
        # ---- FUN & SIGHTS ----
        {
            "category": "fun",
            "name": "Victoria Peak — The Peak",
            "short_desc": "Iconic panoramic views of the Hong Kong skyline and harbour.",
            "full_desc": "The Peak is Hong Kong's most visited attraction, offering breathtaking 360-degree views of the city skyline, Victoria Harbour, and surrounding islands. Take the historic Peak Tram (Asia's oldest funicular railway, since 1888) to the top. The Sky Terrace 428 observation deck provides the best views. The Peak also has shops, restaurants, and easy walking paths.",
            "location": "The Peak, Hong Kong Island",
            "price_range": "Peak Tram: HK$62 (seniors HK$29)",
            "hours": "Peak Tram: 7:00 AM – 12:00 AM",
            "transport": "Peak Tram from Central (Garden Road terminal) or Bus 15 from Central",
            "elderly_friendly": True,
            "tips": ["Senior discount available with HKID", "Visit at sunset for the best views", "The circular walk around the Peak is flat and easy"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Star Ferry — Victoria Harbour",
            "short_desc": "Iconic harbour crossing since 1888. One of the world's best ferry rides.",
            "full_desc": "The Star Ferry has been crossing Victoria Harbour since 1888 and is one of Hong Kong's most beloved experiences. The 10-minute ride between Central and Tsim Sha Tsui offers stunning views of both shorelines. At just a few dollars per trip, it's one of the best bargains in Hong Kong. The Tsim Sha Tsui waterfront promenade is perfect for an evening stroll.",
            "location": "Central Pier ↔ Tsim Sha Tsui Pier",
            "price_range": "HK$3.70–5.60 (seniors HK$2.20)",
            "hours": "6:30 AM – 11:30 PM daily",
            "transport": "MTR Central Station Exit A or Tsim Sha Tsui Station Exit E",
            "elderly_friendly": True,
            "tips": ["Sit on the upper deck for best views", "Senior Octopus card gets discounted fare", "Best at sunset or for the Symphony of Lights at 8 PM"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Nan Lian Garden & Chi Lin Nunnery",
            "short_desc": "Tranquil Tang dynasty-style garden with bonsai, ponds, and a golden pagoda.",
            "full_desc": "Nan Lian Garden is a beautifully maintained Tang dynasty-style garden in the heart of urban Kowloon. Connected to the elegant Chi Lin Nunnery, the garden features manicured bonsai, lotus ponds, waterfalls, rocky hills, and the stunning golden Pavilion of Absolute Perfection. A serene escape from the city. Free entry.",
            "location": "Diamond Hill, Kowloon",
            "price_range": "Free entry",
            "hours": "7:00 AM – 9:00 PM daily",
            "transport": "MTR Diamond Hill Station Exit C2",
            "elderly_friendly": True,
            "tips": ["Completely free — one of HK's best free attractions", "Flat, wheelchair-accessible paths throughout", "Try the vegetarian restaurant inside Chi Lin Nunnery"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Hong Kong Wetland Park",
            "short_desc": "Nature reserve with bird-watching, butterfly gardens, and mangroves.",
            "full_desc": "Hong Kong Wetland Park is a 61-hectare nature reserve in Tin Shui Wai featuring indoor galleries, outdoor wetland habitats, bird hides, a butterfly garden, and mangrove boardwalks. Watch for the park's resident crocodile 'Pui Pui'. Educational and relaxing, it's a wonderful day out for nature lovers of all ages.",
            "location": "Tin Shui Wai, New Territories",
            "price_range": "HK$30 (seniors HK$15)",
            "hours": "10:00 AM – 5:00 PM (closed Tuesdays)",
            "transport": "MTR Wetland Park Station, 5 min walk",
            "elderly_friendly": True,
            "tips": ["Bring binoculars for bird-watching", "Flat boardwalks suitable for wheelchairs", "Best visited in autumn for migratory birds"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Temple Street Night Market",
            "short_desc": "Atmospheric night market with food stalls, fortune tellers, and street opera.",
            "full_desc": "Temple Street Night Market comes alive after dark with hundreds of street stalls, open-air food vendors (try the clay pot rice and typhoon shelter crab), fortune tellers, and sometimes traditional Cantonese street opera. It's a vibrant window into old Hong Kong culture. The market is named after the Tin Hau Temple at its centre.",
            "location": "Temple Street, Yau Ma Tei & Jordan",
            "price_range": "HK$50–200 per person (food & shopping)",
            "hours": "4:00 PM – 12:00 AM daily (best after 7 PM)",
            "transport": "MTR Jordan Station Exit A or Yau Ma Tei Station Exit C",
            "elderly_friendly": True,
            "tips": ["Best atmosphere after 7 PM when fully open", "Try the dai pai dong street food near Temple Street", "Visit Tin Hau Temple for a cultural experience"],
            "url": "#"
        },
        # ---- EVENTS ----
        {
            "category": "events",
            "name": "Chinese New Year Celebrations 2026",
            "short_desc": "Fireworks, night parade, flower markets across Hong Kong.",
            "full_desc": "Chinese New Year 2026 (Year of the Horse) falls on 17 February. Key events include the spectacular fireworks display over Victoria Harbour, the international night parade in Tsim Sha Tsui, and traditional flower markets (年宵市場) across all districts. Victoria Park hosts the largest flower market. Temples are busy with worshippers on New Year's Day.",
            "location": "Citywide — Victoria Harbour, Tsim Sha Tsui, Victoria Park",
            "price_range": "Mostly free",
            "hours": "Various dates around 17 Feb 2026",
            "transport": "MTR to respective locations",
            "elderly_friendly": True,
            "tips": ["Flower markets start about a week before New Year", "Victoria Harbour fireworks best viewed from Tsim Sha Tsui waterfront", "Wear red for good luck!"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "Cheung Chau Bun Festival 2026",
            "short_desc": "Unique annual festival with bun-snatching competition and Piu Sik parades.",
            "full_desc": "The Cheung Chau Bun Festival (太平清醮) is a unique annual Taoist festival held on the tiny island of Cheung Chau. Highlights include the famous bun-snatching competition where participants climb 14-metre bun towers, and the colourful Piu Sik (飄色) parade with children suspended in the air wearing elaborate costumes. A truly unique Hong Kong cultural experience.",
            "location": "Cheung Chau Island",
            "price_range": "Free (ferry ticket required)",
            "hours": "May 2026 (dates vary by lunar calendar)",
            "transport": "Ferry from Central Pier 5 to Cheung Chau (35-55 min)",
            "elderly_friendly": True,
            "tips": ["Arrive early — ferries get very crowded", "The island is small & walkable", "Try the festival buns (平安包) sold everywhere"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "Mid-Autumn Festival Lantern Displays",
            "short_desc": "Spectacular lantern displays in Victoria Park and across HK districts.",
            "full_desc": "The Mid-Autumn Festival features stunning traditional and modern lantern displays across Hong Kong. Victoria Park hosts the largest display with themed lanterns, live performances, and traditional games. Many districts set up their own displays at local parks. People carry lanterns, eat mooncakes, and enjoy the full moon together. A wonderful family-friendly festival.",
            "location": "Victoria Park, Tai Hang (Fire Dragon), various districts",
            "price_range": "Free",
            "hours": "September 2026 (15th day of 8th lunar month)",
            "transport": "MTR Tin Hau Station for Victoria Park",
            "elderly_friendly": True,
            "tips": ["Don't miss the Tai Hang Fire Dragon Dance — a three-night tradition", "Try different mooncake flavours at local bakeries", "Bring a lantern to join the celebrations"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "Hong Kong Hiking Festival (Autumn)",
            "short_desc": "Organized senior-friendly hikes with guides on scenic HK trails.",
            "full_desc": "Autumn in Hong Kong (October–December) is the best hiking season with cool, dry weather. Many organizations host guided group hikes suitable for seniors, including easy routes along the Dragon's Back, Lamma Island Family Trail, and Tai Tam Reservoir path. These organized events often include transport, lunch, and experienced guides. A great way to socialize and stay active.",
            "location": "Various trails across Hong Kong",
            "price_range": "Free to HK$100 (organized events)",
            "hours": "October – December 2026",
            "transport": "Varies by trail",
            "elderly_friendly": True,
            "tips": ["Dragon's Back and Lamma Family Trail are easiest", "Bring water and wear comfortable shoes", "Check LCSD or hiking groups for organized senior events"],
            "url": "#"
        },
    ],
    "zh-HK": [
        # ---- 美食 ----
        {
            "category": "food",
            "name": "添好運 — 點心",
            "short_desc": "全球最平米芝蓮一星餐廳。招牌酥皮焗叉燒包好出名。",
            "full_desc": "添好運係全球最平嘅米芝蓮一星餐廳，招牌酥皮焗叉燒包外層酥脆帶甜，內餡叉燒鬆軟惹味。點心款式豐富，全部即點即蒸，新鮮熱辣。價錢親民，幾十蚊已經食到飽。分店遍布全港各區。",
            "location": "深水埗、旺角、中環（多間分店）",
            "price_range": "每位 HK$50–150",
            "hours": "每日 10:00 – 21:30",
            "transport": "港鐵深水埗站 B2 出口（原店）",
            "elderly_friendly": True,
            "tips": ["早啲去排隊會快好多", "一定要試招牌酥皮焗叉燒包", "大部分分店都有升降機"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "麥奀記 — 雲吞麵",
            "short_desc": "傳奇雲吞麵，1920年代至今。幼細彈牙竹昇麵配鮮蝦雲吞。",
            "full_desc": "麥奀記有近百年歷史，係香港最出名嘅雲吞麵之一。手打竹昇麵幼細彈牙，配上鮮甜蝦湯底同埋飽滿嘅鮮蝦雲吞。簡單、實惠、好食。每碗都係對傳統嘅堅持。",
            "location": "中環威靈頓街",
            "price_range": "每位 HK$40–80",
            "hours": "每日 11:00 – 20:00",
            "transport": "港鐵中環站 D2 出口，步行5分鐘",
            "elderly_friendly": True,
            "tips": ["份量唔大，啱晒一次試幾款", "部分分店淨收現金", "有冷氣座位"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "泰昌餅家 — 蛋撻",
            "short_desc": "全港最出名嘅蛋撻。酥皮鬆化，蛋漿嫩滑香甜。",
            "full_desc": "泰昌餅家自1954年開業，蛋撻係佢嘅招牌。末代港督彭定康都係佢嘅忠實粉絲，所以又叫做「肥彭蛋撻」。酥皮層層鬆化，蛋漿嫩滑帶甜，每一啖都充滿港式風味。必試之選。",
            "location": "中環擺花街（原店）；多間分店",
            "price_range": "每個蛋撻 HK$10–15",
            "hours": "每日 7:30 – 21:00",
            "transport": "港鐵中環站 D2 出口",
            "elderly_friendly": True,
            "tips": ["趁熱食最好味 — 可以問佢攞新鮮出爐嘅", "蛋撻配奶茶係絕配", "中環原店最有懷舊味"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "澳洲牛奶公司",
            "short_desc": "傳奇茶餐廳，炒蛋多士同燉奶極受歡迎。",
            "full_desc": "呢間70年代風格嘅茶餐廳以超滑炒蛋多士同蒸燉奶聞名。服務員出名快手快腳，坐低就要即叫。可能要同人搭枱。係最正宗嘅香港早餐體驗。",
            "location": "佐敦，九龍",
            "price_range": "每位 HK$30–60",
            "hours": "7:30 – 23:00（逢星期四休息）",
            "transport": "港鐵佐敦站 C2 出口",
            "elderly_friendly": True,
            "tips": ["坐低之前諗定叫咩 — 服務好快㗎", "必試：炒蛋多士 + 奶茶", "預咗要搭枱"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "鯉魚門海鮮街",
            "short_desc": "自己揀活海鮮，對住海景食新鮮即煮海鮮。",
            "full_desc": "鯉魚門係一個漁村變成嘅海鮮天堂，可以喺海鮮檔揀活海鮮，然後拎到旁邊嘅食肆代煮。對住海港景色食新鮮魚、蝦、龍蝦、蟹，好寫意。係一個好適合半日遊嘅好去處。",
            "location": "鯉魚門，觀塘，九龍",
            "price_range": "每位 HK$150–400",
            "hours": "每日 11:00 – 22:00",
            "transport": "港鐵油塘站 A2 出口，轉小巴24",
            "elderly_friendly": True,
            "tips": ["多行幾檔比較價錢", "加工費同海鮮價錢係分開計", "黃昏景色特別靚"],
            "url": "#"
        },
        # ---- 購物 ----
        {
            "category": "shopping",
            "name": "女人街 — 通菜街",
            "short_desc": "旺角人氣露天市場，衫褲鞋襪飾物樣樣平。",
            "full_desc": "女人街喺通菜街，成個市場成成一公里長，有幾百個攤檔賣平價衫褲、手袋、飾物、手機殼、紀念品同日用品。雖然叫女人街，但係男女老幼都啱去。旺角最熱鬧嘅市集體驗。",
            "location": "旺角通菜街",
            "price_range": "每件 HK$10–200",
            "hours": "每日 12:00 – 23:30",
            "transport": "港鐵旺角站 D3 出口",
            "elderly_friendly": True,
            "tips": ["講價係常識，可以由一半開始還", "下晝先至最多嘢揀", "人多注意銀包財物"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "赤柱市場",
            "short_desc": "海邊市集，有藝術品、衫褲同海景餐廳。",
            "full_desc": "赤柱市場係港島南區嘅海邊市集，可以買到藝術品、絲綢衫、中式古董、休閒服同紀念品。行完街可以去海邊食海鮮，環境優美。離開市區半日遊好選擇。",
            "location": "赤柱，港島南",
            "price_range": "價錢唔一",
            "hours": "每日 10:00 – 18:00",
            "transport": "中環（交易廣場）搭巴士 6、6X、260",
            "elderly_friendly": True,
            "tips": ["順便去赤柱沙灘行吓", "海邊餐廳景色一流", "平日去人少好多"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "玉器市場 — 油麻地",
            "short_desc": "傳統玉器市場，有幾百個攤檔賣各式中國玉器。",
            "full_desc": "油麻地玉器市場有超過400個攤檔，賣玉器首飾、擺設同玉雕。玉器喺中國文化裏面代表好運、健康同長壽。無論係小吊墜定精緻玉鐲，呢度應有盡有。旁邊仲有廟街夜市。",
            "location": "油麻地甘肅街",
            "price_range": "HK$50–5,000+",
            "hours": "每日 10:00 – 17:00",
            "transport": "港鐵油麻地站 C 出口",
            "elderly_friendly": True,
            "tips": ["帶現金會有更好價錢", "貴嘅玉器記得要求證書", "晚上順便行廟街夜市"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "深水埗布藝及電子商場",
            "short_desc": "平價天堂，布藝、電子產品同懷舊雜貨。",
            "full_desc": "深水埗係香港最地道嘅草根社區，平價布藝、製衣材料、珠仔材料同電子產品應有盡有。黃金電腦商場有最平嘅電子產品。呢區仲有好多好味街頭小食。",
            "location": "深水埗，九龍",
            "price_range": "非常平",
            "hours": "每日 10:00 – 20:00",
            "transport": "港鐵深水埗站 D2 出口",
            "elderly_friendly": True,
            "tips": ["基隆街一帶有最多布藝舖", "桂林街有好多街頭小食", "黃金電腦商場買電子嘢最平"],
            "url": "#"
        },
        # ---- 玩樂 ----
        {
            "category": "fun",
            "name": "太平山頂",
            "short_desc": "香港最著名嘅觀景點，可以睇到成個維港同城市景色。",
            "full_desc": "太平山頂係香港最受歡迎嘅景點，可以360度睇到城市天際線、維多利亞港同周圍嘅島嶼。搭歷史悠久嘅山頂纜車（亞洲最古老嘅纜索鐵路，1888年至今）上去。凌霄閣觀景台428係最佳觀景位置。山頂仲有商店、餐廳同易行嘅步行徑。",
            "location": "太平山，港島",
            "price_range": "山頂纜車：HK$62（長者 HK$29）",
            "hours": "山頂纜車：7:00 – 00:00",
            "transport": "中環花園道搭山頂纜車或中環搭巴士15號",
            "elderly_friendly": True,
            "tips": ["長者持香港身份證有優惠", "日落時分去景色最靚", "環山步行徑平坦易行"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "天星小輪 — 維多利亞港",
            "short_desc": "1888年至今嘅經典渡輪，世界最佳渡輪體驗之一。",
            "full_desc": "天星小輪自1888年穿梭維港，係香港最受歡迎嘅體驗之一。10分鐘嘅船程由中環去到尖沙咀，兩岸景色盡收眼底。幾蚊雞就搭到，性價比極高。尖沙咀海濱長廊好適合傍晚散步。",
            "location": "中環碼頭 ↔ 尖沙咀碼頭",
            "price_range": "HK$3.70–5.60（長者 HK$2.20）",
            "hours": "每日 6:30 – 23:30",
            "transport": "港鐵中環站 A 出口或尖沙咀站 E 出口",
            "elderly_friendly": True,
            "tips": ["坐上層景色最好", "長者八達通有優惠", "日落或晚上8點幻彩詠香江最靚"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "南蓮園池 & 志蓮淨苑",
            "short_desc": "寧靜唐式園林，有盆景、荷花池同金色涼亭。",
            "full_desc": "南蓮園池係一個保養得好靚嘅唐朝風格園林，位於城市中心嘅鑽石山。連住典雅嘅志蓮淨苑，園內有精心修剪嘅盆景、荷花池、瀑布、假山同華麗嘅金色圓滿閣。城市中嘅寧靜角落。免費入場。",
            "location": "鑽石山，九龍",
            "price_range": "免費入場",
            "hours": "每日 7:00 – 21:00",
            "transport": "港鐵鑽石山站 C2 出口",
            "elderly_friendly": True,
            "tips": ["完全免費，係香港最佳免費景點之一", "全園平坦，輪椅都行到", "可以試吓志蓮淨苑入面嘅素食餐廳"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "香港濕地公園",
            "short_desc": "自然保護區，有觀鳥、蝴蝶園同紅樹林木板步道。",
            "full_desc": "香港濕地公園位於天水圍，佔地61公頃，有室內展覽館、戶外濕地生態、觀鳥屋、蝴蝶園同紅樹林步道。仲可以睇到公園嘅明星鱷魚「貝貝」。既有教育意義又輕鬆寫意，適合各年齡層嘅自然愛好者。",
            "location": "天水圍，新界",
            "price_range": "HK$30（長者 HK$15）",
            "hours": "10:00 – 17:00（逢星期二休園）",
            "transport": "港鐵濕地公園站，步行5分鐘",
            "elderly_friendly": True,
            "tips": ["帶望遠鏡觀鳥更有趣", "木板步道平坦，輪椅都行到", "秋天嚟最好，可以睇到候鳥"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "廟街夜市",
            "short_desc": "有氣氛嘅夜市，有街頭小食、占卜同粵劇。",
            "full_desc": "廟街夜市天黑後最熱鬧，有幾百個街邊攤檔、露天大牌檔（試吓煲仔飯同避風塘炒蟹）、占卜攤同偶爾嘅粵劇表演。係睇舊香港文化嘅好地方。夜市以中間嘅天后廟命名。",
            "location": "廟街，油麻地及佐敦",
            "price_range": "每位 HK$50–200（食嘢同購物）",
            "hours": "每日 16:00 – 00:00（19:00後最旺）",
            "transport": "港鐵佐敦站 A 出口或油麻地站 C 出口",
            "elderly_friendly": True,
            "tips": ["晚上7點後最有氣氛", "試吓廟街附近嘅大牌檔小食", "去天后廟參拜感受文化"],
            "url": "#"
        },
        # ---- 活動 ----
        {
            "category": "events",
            "name": "2026 農曆新年慶祝活動",
            "short_desc": "維港煙花、花車巡遊、年宵花市遍布全港。",
            "full_desc": "2026年農曆新年（馬年）喺2月17日。重點活動包括維港上空嘅壯觀煙花匯演、尖沙咀國際花車巡遊、同遍布全港嘅年宵花市。維園有最大嘅花市。年初一各大廟宇會好多人拜神。",
            "location": "全港 — 維港、尖沙咀、維園",
            "price_range": "大部分免費",
            "hours": "2026年2月17日前後",
            "transport": "港鐵到相關地點",
            "elderly_friendly": True,
            "tips": ["年宵花市喺新年前一個禮拜開始", "維港煙花喺尖沙咀海邊睇最靚", "著紅色衫代表好運！"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "2026 長洲太平清醮",
            "short_desc": "獨特年度節慶，有搶包山比賽同飄色巡遊。",
            "full_desc": "長洲太平清醮係一個好特別嘅年度道教節日，喺長洲島舉行。重點包括出名嘅搶包山比賽（參加者要爬上14米高嘅包山）同色彩繽紛嘅飄色巡遊（小朋友著住靚衫凌空飛起）。真係獨一無二嘅香港文化體驗。",
            "location": "長洲島",
            "price_range": "免費（需要買船票）",
            "hours": "2026年5月（日期按農曆定）",
            "transport": "中環5號碼頭搭渡輪去長洲（35-55分鐘）",
            "elderly_friendly": True,
            "tips": ["早啲去碼頭，船會好迫", "島仔唔大，行路就得", "記得買「平安包」食"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "中秋節花燈會",
            "short_desc": "維園同各區公園嘅大型花燈展覽。",
            "full_desc": "中秋節有壯觀嘅傳統同現代花燈展覽遍布全港。維園有最大型嘅花燈會，有主題花燈、現場表演同傳統遊戲。好多區都會喺當地公園搞花燈展。市民會提燈籠、食月餅、賞月。好適合一家大細嘅節日。",
            "location": "維園、大坑（舞火龍）、各區",
            "price_range": "免費",
            "hours": "2026年9月（農曆八月十五）",
            "transport": "港鐵天后站去維園",
            "elderly_friendly": True,
            "tips": ["一定唔好錯過大坑舞火龍 — 一連三晚嘅傳統", "試吓唔同口味嘅月餅", "帶個燈籠一齊玩"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "秋季香港行山節",
            "short_desc": "有導賞嘅長者友善行山團，行香港靚景山徑。",
            "full_desc": "香港秋天（10至12月）係最佳行山季節，天氣涼爽乾燥。好多機構會搞適合長者嘅導賞行山團，包括輕鬆路線如龍脊、南丫島家樂徑同大潭水塘路。有啲活動包交通、午餐同經驗豐富嘅導遊。係保持活躍同社交嘅好方法。",
            "location": "全港各行山徑",
            "price_range": "免費至 HK$100（有組織活動）",
            "hours": "2026年10月至12月",
            "transport": "視乎路線而定",
            "elderly_friendly": True,
            "tips": ["龍脊同南丫島家樂徑最輕鬆", "記得帶水同著舒服嘅鞋", "留意康文署或行山群組嘅長者活動"],
            "url": "#"
        },
    ]
}




def get_hk_guide_data(lang: str = 'en') -> list[dict]:
    """Return curated HK local guide data for the given language."""
    return HK_GUIDE_DATA.get(lang, HK_GUIDE_DATA["en"])
