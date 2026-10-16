from typing import Literal

ChunkPolicy = Literal["prose_tables", "numeric"]
ChunkTypes = Literal["prose_tables", "rows"]
CHUNK_POLICIES: tuple[ChunkPolicy, ...] = ("prose_tables", "numeric")
