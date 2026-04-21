import logging
from config import ANTHROPIC_API_KEY, DEFAULT_MODEL

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._client = None
        self._available = False

        if ANTHROPIC_API_KEY:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                self._available = True
                logger.info(f"LLM client initialized with model: {self.model}")
            except ImportError:
                logger.warning("anthropic package not installed. Run: pip install anthropic")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM client: {e}")
        else:
            logger.warning("ANTHROPIC_API_KEY not set. LLM features disabled.")

    @property
    def available(self) -> bool:
        return self._available

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        if not self._available:
            return "[LLM unavailable — set ANTHROPIC_API_KEY to enable AI analysis]"

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": prompt}],
            )
            for block in response.content:
                if block.type == "text":
                    return block.text
            return ""
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return f"[LLM error: {e}]"
