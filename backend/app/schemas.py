from typing import Annotated

from pydantic import BaseModel, StringConstraints

MAX_TOPIC_LENGTH = 2000

Topic = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TOPIC_LENGTH)]


class GenerateRequest(BaseModel):
    topic: Topic


class GenerateResponse(BaseModel):
    topic: str
    draft: str
    critique: str
    revised: str


class HealthResponse(BaseModel):
    status: str
