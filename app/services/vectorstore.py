class VectorStore:
    def __init__(self, qdrant_url: str):
        # client setup
        pass

    async def upsert(self, items: list[dict]):
        """index items: {id, text, embedding, metadata}"""
        ...

    async def query(self, query_embedding, top_k=5, filters=None):
        """return top_k chunks with metadata"""
        ...
