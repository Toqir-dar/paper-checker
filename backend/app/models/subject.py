from pydantic import BaseModel, Field


class Subject(BaseModel):
    id: str | None = Field(default=None, validation_alias="_id", serialization_alias="id")
    name: str = Field(min_length=1, max_length=100)

    model_config = {"populate_by_name": True}