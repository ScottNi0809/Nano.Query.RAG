import json
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

QUERY_REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a query optimization assistant. Your job is to rewrite user "
            "questions so they work better for document retrieval in a RAG system.\n\n"
            "Rules:\n"
            "1. If the question is already clear and focused, return it as-is.\n"
            "2. If the question is vague or ambiguous, make it more specific.\n"
            "3. If the question contains multiple sub-questions, decompose it into "
            "individual focused queries.\n"
            "4. Remove filler words and conversational noise.\n"
            "5. Preserve the original intent and all technical terms.\n\n"
            "Respond with a JSON object in this exact format:\n"
            '{{"queries": ["query1", "query2", ...]}}\n\n'
            "For simple questions, the list should contain a single rewritten query. "
            "For complex multi-part questions, include one query per sub-question "
            "(maximum 3 queries).",
        ),
        ("human", "{question}"),
    ]
)


class QueryRewriteResult:
    __slots__ = ("queries", "original")

    def __init__(self, queries: list[str], original: str):
        self.queries = queries
        self.original = original


class QueryRewriteService:
    def __init__(self, chat_model: BaseChatModel):
        self._chain = QUERY_REWRITE_PROMPT | chat_model | StrOutputParser()

    async def rewrite(self, question: str) -> QueryRewriteResult:
        raw = await self._chain.ainvoke({"question": question})
        queries = self._parse_response(raw, question)
        if queries != [question]:
            logger.info("Query rewritten: %r -> %r", question, queries)
        return QueryRewriteResult(queries=queries, original=question)

    @staticmethod
    def _parse_response(raw: str, fallback: str) -> list[str]:
        try:
            data = json.loads(raw)
            queries = data.get("queries", [])
            if isinstance(queries, list) and all(isinstance(q, str) and q.strip() for q in queries):
                return [q.strip() for q in queries[:3]]
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Failed to parse query rewrite response: %s", raw)
        return [fallback]
