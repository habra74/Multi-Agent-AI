"""
news_agent.py
-------------
Analyzes recent news headlines and classifies them by sentiment and event category.

Rule-based mode:
  - Keyword-based sentiment scoring
  - Event category detection (earnings, product, analyst, legal, macro, etc.)
  - Structured evidence list with per-article metadata (headline, interpretation, link)

LLM mode (requires ANTHROPIC_API_KEY):
  - Loads prompt from prompts/news_agent_prompt.txt
  - Returns richer qualitative summary and nuanced sentiment
"""

import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent
from models.llm import LLMClient
from tools.utils import clamp

# ---------------------------------------------------------------------------
# Keyword taxonomy
# ---------------------------------------------------------------------------

CATEGORIES: Dict[str, List[str]] = {
    "earnings":  ["earnings", "eps", "beat", "miss", "revenue", "profit", "guidance",
                  "quarter", "q1", "q2", "q3", "q4", "annual results", "fiscal"],
    "product":   ["launch", "release", "unveil", "announce", "new product", "new model",
                  "iphone", "ipad", "macbook", "vision pro", "feature", "update"],
    "analyst":   ["upgrade", "downgrade", "target", "price target", "overweight",
                  "underweight", "buy rating", "sell rating", "analyst", "initiate"],
    "legal":     ["lawsuit", "sue", "court", "ruling", "penalty", "fine", "settlement",
                  "investigation", "probe", "antitrust", "regulation", "sec", "doj"],
    "macro":     ["fed", "interest rate", "inflation", "gdp", "recession", "tariff",
                  "trade war", "china", "supply chain", "economy"],
    "corporate": ["acquisition", "merger", "buyback", "dividend", "ipo", "spinoff",
                  "layoff", "restructure", "ceo", "executive", "partnership", "deal"],
    "sentiment": ["surge", "rally", "plunge", "crash", "soar", "tumble", "volatile",
                  "strong", "weak", "concern", "optimism", "pessimism"],
}

POSITIVE_KEYWORDS: List[str] = [
    "upgrade", "beat", "record", "growth", "launch", "partnership", "buyback",
    "dividend", "approval", "expansion", "acquisition", "patent", "contract",
    "profit", "innovation", "strong", "rally", "surge", "deal", "momentum",
    "milestone", "outperform", "raise", "positive", "bullish", "overweight",
    "top line", "bottom line", "guidance raised", "exceeds", "outperform",
]

NEGATIVE_KEYWORDS: List[str] = [
    "lawsuit", "fraud", "investigation", "downgrade", "miss", "loss", "cut",
    "layoff", "recall", "scandal", "bankruptcy", "decline", "fall", "drop",
    "concern", "risk", "warn", "penalty", "fine", "regulation", "short",
    "disappoints", "uncertainty", "headwind", "pressure", "below", "guidance cut",
    "underperform", "sell", "bearish", "debt", "writedown", "impairment",
]

# ---------------------------------------------------------------------------
# Korean category/sentiment labels
# ---------------------------------------------------------------------------

CATEGORY_KO: Dict[str, str] = {
    "earnings":  "실적",
    "product":   "제품",
    "analyst":   "애널리스트",
    "legal":     "법률/규제",
    "macro":     "거시경제",
    "corporate": "기업이슈",
    "sentiment": "시장심리",
    "general":   "일반",
}

# Korean interpretation templates: category → sentiment → message
INTERPRETATION_MAP: Dict[str, Dict[str, str]] = {
    "earnings": {
        "positive": "실적 개선 기대감이 반영되어 주가에 긍정적 영향이 예상됩니다.",
        "negative": "실적 부진 우려로 단기 주가 하락 압력이 있을 수 있습니다.",
        "neutral":  "향후 실적 발표 결과를 면밀히 주시할 필요가 있습니다.",
        "mixed":    "실적 관련 엇갈린 신호가 포착되어 방향성 확인이 필요합니다.",
    },
    "analyst": {
        "positive": "애널리스트 긍정적 시각이 반영되어 목표가 상향 가능성에 주목하십시오.",
        "negative": "투자의견 하향 등 부정적 애널리스트 시각에 유의하십시오.",
        "neutral":  "애널리스트 커버리지 변화를 지속적으로 모니터링하십시오.",
        "mixed":    "애널리스트 의견이 엇갈려 추가 시각 확인이 필요합니다.",
    },
    "legal": {
        "positive": "법적·규제 리스크가 완화되어 불확실성이 감소할 수 있습니다.",
        "negative": "법적 분쟁·규제 리스크가 잠재적 비용 증가 요인으로 작용할 수 있습니다.",
        "neutral":  "규제 및 법적 동향을 지속적으로 모니터링하십시오.",
        "mixed":    "법적 이슈의 진행 경과를 면밀히 살펴볼 필요가 있습니다.",
    },
    "product": {
        "positive": "신제품·서비스 출시로 매출 성장 기대감이 높아지고 있습니다.",
        "negative": "제품 관련 부정적 소식이 수요 전망에 영향을 줄 수 있습니다.",
        "neutral":  "제품 반응 및 시장 수요를 지켜봐야 합니다.",
        "mixed":    "제품 관련 혼재된 신호가 포착되어 추가 확인이 필요합니다.",
    },
    "macro": {
        "positive": "거시경제 환경 개선이 업황에 긍정적으로 작용하고 있습니다.",
        "negative": "거시경제 불확실성이 단기 주가에 부담을 줄 수 있습니다.",
        "neutral":  "거시환경 변화가 해당 업종에 미치는 영향을 점검하십시오.",
        "mixed":    "거시 변수가 복잡하게 얽혀 있어 방향성 판단에 신중이 요구됩니다.",
    },
    "corporate": {
        "positive": "기업 이벤트(M&A·배당·자사주 등)가 주주가치 제고에 기여할 수 있습니다.",
        "negative": "기업 구조 변화에 따른 불확실성에 유의하십시오.",
        "neutral":  "기업 이벤트 내용 및 시장 반응을 구체적으로 확인하십시오.",
        "mixed":    "기업 이슈의 긍부정 효과를 복합적으로 검토할 필요가 있습니다.",
    },
}

_GENERAL_INTERP: Dict[str, str] = {
    "positive": "긍정적 뉴스 흐름이 단기 주가에 호재로 작용할 수 있습니다.",
    "negative": "부정적 뉴스 흐름이 단기 주가에 하락 압력을 가할 수 있습니다.",
    "neutral":  "시장 반응을 주시하며 추가 정보 확인이 필요합니다.",
    "mixed":    "엇갈린 뉴스 흐름으로 방향성 확인이 필요합니다.",
}


def _make_interpretation(sentiment: str, category: str) -> str:
    """Return a Korean investment interpretation sentence."""
    cat_map = INTERPRETATION_MAP.get(category, {})
    return cat_map.get(sentiment, _GENERAL_INTERP.get(sentiment, _GENERAL_INTERP["neutral"]))


def _category_ko(category: str) -> str:
    return CATEGORY_KO.get(category, category)


# ---------------------------------------------------------------------------
# NewsAgent
# ---------------------------------------------------------------------------

class NewsAgent(BaseAgent):
    """Analyzes recent news and returns sentiment, categories, and structured evidence."""

    def __init__(self):
        super().__init__("news_agent")
        self.llm = LLMClient()
        self._prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load LLM prompt from file; fall back to inline default."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "news_agent_prompt.txt"
        try:
            return prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, input_data: dict) -> dict:
        """
        Analyze news for a ticker.

        Expected input keys:
            news_data (list), ticker (str), financial_data (dict)
        """
        news_data: list = input_data.get("news_data", [])
        ticker: str = input_data.get("ticker", "N/A")
        financial: dict = input_data.get("financial_data", {})
        company: str = financial.get("company_name", ticker)

        # Defensive: filter out items with no title
        valid_news = [n for n in news_data if n.get("title", "").strip()]

        if not valid_news:
            self.logger.warning(f"No usable news items for {ticker} "
                                f"(raw: {len(news_data)})")
            return self._no_news_result(ticker)

        self.logger.info(f"Analyzing {len(valid_news)} news items for {ticker}")

        # Classify each article
        classified = [self._classify_article(item) for item in valid_news]

        if self.llm.available:
            return self._llm_analysis(classified, ticker, company)
        return self._rule_based_analysis(classified, ticker, company)

    # ------------------------------------------------------------------
    # Article classification (shared by both modes)
    # ------------------------------------------------------------------

    def _classify_article(self, item: dict) -> dict:
        """Attach sentiment score and event category to a news item."""
        title = item.get("title", "")
        title_lower = title.lower()

        pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in title_lower)
        neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in title_lower)

        if pos > neg:
            sentiment = "positive"
        elif neg > pos:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        category = self._detect_category(title_lower)

        return {
            **item,
            "sentiment": sentiment,
            "pos_score": pos,
            "neg_score": neg,
            "category": category,
        }

    def _detect_category(self, title_lower: str) -> str:
        """Return the best-matching event category."""
        hits: Dict[str, int] = {}
        for cat, keywords in CATEGORIES.items():
            count = sum(1 for kw in keywords if kw in title_lower)
            if count:
                hits[cat] = count
        if not hits:
            return "general"
        return max(hits, key=hits.get)

    # ------------------------------------------------------------------
    # Rule-based analysis
    # ------------------------------------------------------------------

    def _rule_based_analysis(self, classified: List[dict], ticker: str, company: str) -> dict:
        """Keyword-based sentiment aggregation with structured evidence."""
        bull_points: List[str] = []
        bear_points: List[str] = []
        evidence: List[dict] = []

        total_pos = 0
        total_neg = 0

        for item in classified[:10]:
            total_pos += item["pos_score"]
            total_neg += item["neg_score"]

            # Build structured evidence entry (include link and Korean interpretation)
            interp = _make_interpretation(item["sentiment"], item["category"])
            evidence.append({
                "headline":       item["title"][:120],
                "publisher":      item.get("publisher", ""),
                "date":           item.get("published", ""),
                "sentiment":      item["sentiment"],
                "category":       item["category"],
                "link":           item.get("link", ""),
                "interpretation": interp,
            })

            # Generate Korean signal points
            title_short = item["title"][:80]
            cat = item["category"]
            cat_label = _category_ko(cat)
            if item["sentiment"] == "positive" and cat in ("earnings", "analyst", "product", "corporate"):
                bull_points.append(f"[{cat_label}] {title_short}")
            elif item["sentiment"] == "negative" and cat in ("earnings", "legal", "macro", "corporate"):
                bear_points.append(f"[{cat_label}] {title_short}")

        # Aggregate sentiment
        total = total_pos + total_neg
        if total == 0:
            sentiment = "neutral"
            confidence = 0.40
        elif total_pos >= total_neg * 1.5:
            sentiment = "positive"
            confidence = clamp(0.50 + (total_pos - total_neg) / max(total * 2, 1))
        elif total_neg >= total_pos * 1.5:
            sentiment = "negative"
            confidence = clamp(0.50 - (total_neg - total_pos) / max(total * 2, 1))
        else:
            sentiment = "mixed"
            confidence = 0.40

        # Category frequency summary (Korean)
        cat_counts: Dict[str, int] = {}
        for item in classified:
            cat_counts[item["category"]] = cat_counts.get(item["category"], 0) + 1
        top_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        cat_summary = ", ".join(f"{_category_ko(c)}({n}건)" for c, n in top_cats)

        sentiment_ko = {
            "positive": "긍정적", "negative": "부정적",
            "neutral": "중립적", "mixed": "혼재",
        }.get(sentiment, sentiment)

        summary = (
            f"{ticker} 뉴스 분석: {len(classified)}건 기사에서 {sentiment_ko} 심리 감지. "
            f"주요 주제: {cat_summary}. "
            f"긍정 신호 {total_pos}개 | 부정 신호 {total_neg}개."
        )

        self.logger.info(f"Rule-based news: sentiment={sentiment}, "
                         f"pos={total_pos}, neg={total_neg}, articles={len(classified)}")

        return {
            "agent_name": self.name,
            "summary": summary,
            "bull_points": bull_points[:4],
            "bear_points": bear_points[:4],
            "confidence": confidence,
            "evidence": evidence,
            "sentiment": sentiment,
            "news_count": len(classified),
            "category_breakdown": cat_counts,
        }

    # ------------------------------------------------------------------
    # LLM analysis
    # ------------------------------------------------------------------

    def _llm_analysis(self, classified: List[dict], ticker: str, company: str) -> dict:
        """Use Claude to produce richer qualitative news analysis."""
        headlines_block = "\n".join(
            f"- [{item.get('published', 'N/A')}] [{item['category'].upper()}] "
            f"{item['title']} ({item.get('publisher', '')})"
            for item in classified[:12]
        )

        if self._prompt_template:
            prompt = self._prompt_template.format(
                company=company, ticker=ticker, headlines=headlines_block
            )
        else:
            prompt = (
                f"You are a financial news analyst. Analyze these recent headlines for "
                f"{company} ({ticker}):\n\n{headlines_block}\n\n"
                "Respond in EXACTLY this format:\n"
                "SENTIMENT: [positive/neutral/negative/mixed]\n"
                "BULL: [key bullish finding]\n"
                "BULL: [second bullish finding if any]\n"
                "BEAR: [key bearish finding]\n"
                "BEAR: [second bearish finding if any]\n"
                "SUMMARY: [2-3 sentence qualitative summary]\n"
                "WATCH: [one news category or topic to monitor]\n"
            )

        response = self.llm.generate(prompt, max_tokens=600)

        sentiment = "neutral"
        bull_points: List[str] = []
        bear_points: List[str] = []
        summary = f"{ticker} 뉴스 LLM 분석 완료."
        watch_items: List[str] = []

        for line in response.split("\n"):
            line = line.strip()
            if not line:
                continue
            key, _, val = line.partition(":")
            val = val.strip()
            key = key.strip().upper()
            if key == "SENTIMENT" and val.lower() in ("positive", "neutral", "negative", "mixed"):
                sentiment = val.lower()
            elif key == "BULL" and val and not val.startswith("["):
                bull_points.append(val)
            elif key == "BEAR" and val and not val.startswith("["):
                bear_points.append(val)
            elif key == "SUMMARY" and val:
                summary = val
            elif key == "WATCH" and val:
                watch_items.append(val)

        confidence = {"positive": 0.72, "mixed": 0.45, "neutral": 0.50, "negative": 0.28}.get(sentiment, 0.50)

        # Attach structured evidence (with link and Korean interpretation)
        evidence = [
            {
                "headline":       item["title"][:120],
                "publisher":      item.get("publisher", ""),
                "date":           item.get("published", ""),
                "sentiment":      item["sentiment"],
                "category":       item["category"],
                "link":           item.get("link", ""),
                "interpretation": _make_interpretation(item["sentiment"], item["category"]),
            }
            for item in classified[:10]
        ]

        cat_counts: Dict[str, int] = {}
        for item in classified:
            cat_counts[item["category"]] = cat_counts.get(item["category"], 0) + 1

        self.logger.info(f"LLM news: sentiment={sentiment}")

        result = {
            "agent_name": self.name,
            "summary": summary,
            "bull_points": bull_points[:4],
            "bear_points": bear_points[:4],
            "confidence": confidence,
            "evidence": evidence,
            "sentiment": sentiment,
            "news_count": len(classified),
            "category_breakdown": cat_counts,
        }
        if watch_items:
            result["watch_items"] = watch_items
        return result

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    def _no_news_result(self, ticker: str) -> dict:
        return {
            "agent_name": self.name,
            "summary": f"{ticker}에 대한 최근 뉴스 기사를 찾을 수 없습니다. 뉴스 심리 분석을 건너뜁니다.",
            "bull_points": [],
            "bear_points": ["최근 뉴스 없음 — 단기 모멘텀 파악이 제한적입니다."],
            "confidence": 0.10,
            "evidence": [],
            "sentiment": "neutral",
            "news_count": 0,
            "category_breakdown": {},
        }
