"""
RAG 서비스 - ChromaDB + LangChain 기반 금융 리포트 Q&A

[구성 요소]
  KnowledgeBase  : ChromaDB 래퍼 (리포트 저장 + 유사 검색)
  RAGChain       : LangChain + GPT-4o-mini (컨텍스트 주입 답변 생성)
  init_rag()     : 서버 시작 시 main.py에서 호출
  get_rag_chain(): 라우터에서 RAGChain 싱글턴 반환

[ChromaDB 컬렉션 구조]
  collection: "investment_reports"
  documents : n8n이 생성한 일일 리포트, 뉴스 요약, 리서치 자료
  metadata  : {"source", "date", "type", "sentiment_score"}
"""
import uuid
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings

# ── RAG 싱글턴 ──
_rag_chain_instance: "RAGChain | None" = None


class KnowledgeBase:
    """ChromaDB 기반 금융 리포트 벡터 DB"""

    def __init__(self):
        embeddings = OpenAIEmbeddings(
            model=settings.EMBED_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
        self.db = Chroma(
            collection_name="investment_reports",
            embedding_function=embeddings,
            persist_directory=str(settings.CHROMA_DIR),
        )

    def add_report(
        self,
        content:   str,
        doc_type:  str = "daily_report",
        date:      str = "",
        source:    str = "n8n",
    ) -> int:
        """
        리포트를 청크로 분할하여 ChromaDB에 저장
        반환값: 저장된 청크 수

        [청킹 전략]
        - 500자 단위로 분할 (한국어 기준 약 250단어)
        - 50자 오버랩 (문맥 연속성 유지)
        """
        chunks    = _chunk_text(content, chunk_size=500, overlap=50)
        ids       = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [
            {"source": source, "date": date, "type": doc_type}
            for _ in chunks
        ]
        self.db.add_texts(texts=chunks, ids=ids, metadatas=metadatas)
        return len(chunks)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """의미 기반 유사 리포트 청크 검색"""
        results = self.db.similarity_search_with_relevance_scores(query, k=top_k)
        return [
            {
                "content":  doc.page_content,
                "metadata": doc.metadata,
                "score":    round(score, 3),
            }
            for doc, score in results
            if score > 0.3   # 유사도 0.3 미만은 관련 없음으로 필터링
        ]

    @property
    def count(self) -> int:
        return self.db._collection.count()


class RAGChain:
    """LangChain RAG 파이프라인"""

    SYSTEM_PROMPT = """당신은 시각 장애인을 위한 AI 투자 어시스턴트입니다.
아래 참조 리포트를 바탕으로 질문에 답변하세요.

[답변 규칙]
1. 반드시 참조 리포트에 근거한 답변만 제공
2. 수치는 단위 명시 ("52달러", "5퍼센트" 등)
3. 200자 이내로 간결하게
4. TTS로 읽기 자연스러운 문장 구성
5. 확실하지 않으면 "정보가 부족합니다"라고 명시

[참조 리포트]
{context}"""

    def __init__(self, kb: KnowledgeBase):
        self.kb  = kb
        self.llm = ChatOpenAI(
            model=settings.CHAT_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
            max_tokens=400,
        )
        self._chain = self._build_chain()

    def _build_chain(self):
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human",  "{question}"),
        ])
        return (
            {"context": self._retrieve, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )

    def _retrieve(self, question: str) -> str:
        """질문과 유사한 리포트 청크를 가져와 컨텍스트로 합침"""
        chunks = self.kb.search(question, top_k=5)
        if not chunks:
            return "참조할 리포트가 없습니다. n8n 워크플로우를 먼저 실행하세요."
        return "\n\n---\n".join(c["content"] for c in chunks)

    def query(self, question: str, top_k: int = 5) -> dict:
        sources  = self.kb.search(question, top_k=top_k)
        answer   = self._chain.invoke(question)
        return {
            "answer":           answer,
            "sources":          sources,
            "retrieved_chunks": len(sources),
        }

    def query_without_rag(self, question: str) -> dict:
        """RAG 미사용 - 순수 LLM 답변 (비교용)"""
        answer = self.llm.invoke(question).content
        return {"answer": answer, "sources": [], "retrieved_chunks": 0}


# ── 초기화 함수 ──

async def init_rag():
    """서버 시작 시 RAGChain 초기화 (lifespan에서 호출)"""
    global _rag_chain_instance
    kb = KnowledgeBase()
    _rag_chain_instance = RAGChain(kb)
    print(f"📚 RAG 초기화 완료 (문서 수: {kb.count})")


async def get_rag_chain() -> RAGChain:
    """라우터에서 RAGChain 싱글턴 반환"""
    if _rag_chain_instance is None:
        await init_rag()
    return _rag_chain_instance


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """텍스트를 오버랩 포함 청크로 분할"""
    chunks, start = [], 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c for c in chunks if c.strip()]
