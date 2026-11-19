from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="Expense API")

# In-memory сховище: дані живуть, поки працює процес
users = {}
categories = {}
records = {}
counters = {"user": 0, "category": 0, "record": 0}


def next_id(entity):
    counters[entity] += 1
    return counters[entity]


def error(status_code, error_code, message):
    return JSONResponse(status_code=status_code, content={"error": error_code, "message": message})


def not_found(entity, entity_id):
    return error(404, "not_found", f"{entity} with id {entity_id} not found")


class NameIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)


class RecordIn(BaseModel):
    user_id: int
    category_id: int
    amount: Decimal = Field(gt=0)
    created_at: Optional[datetime] = None  # якщо не передано — поточний час


# Некоректні дані (тіло, query, path) -> 400 замість стандартного 422
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    parts = []
    for err in exc.errors():
        field = ".".join(str(x) for x in err["loc"] if x not in ("body", "query", "path"))
        parts.append(f"{field}: {err['msg']}" if field else err["msg"])
    return error(400, "validation_error", "; ".join(parts))


# Users

@app.get("/users")
def get_users():
    return list(users.values())


@app.get("/user/{user_id}")
def get_user(user_id: int):
    if user_id not in users:
        return not_found("User", user_id)
    return users[user_id]


@app.post("/user", status_code=201)
def create_user(data: NameIn):
    user = {"id": next_id("user"), "name": data.name}
    users[user["id"]] = user
    return user


@app.delete("/user/{user_id}", status_code=204)
def delete_user(user_id: int):
    if user_id not in users:
        return not_found("User", user_id)
    del users[user_id]
    # разом із користувачем видаляємо його записи
    for record_id in [r["id"] for r in records.values() if r["user_id"] == user_id]:
        del records[record_id]
    return Response(status_code=204)


# Categories

@app.get("/category")
def get_categories():
    return list(categories.values())


@app.post("/category", status_code=201)
def create_category(data: NameIn):
    category = {"id": next_id("category"), "name": data.name}
    categories[category["id"]] = category
    return category


@app.delete("/category/{category_id}", status_code=204)
def delete_category(category_id: int):
    if category_id not in categories:
        return not_found("Category", category_id)
    del categories[category_id]
    for record_id in [r["id"] for r in records.values() if r["category_id"] == category_id]:
        del records[record_id]
    return Response(status_code=204)


# Records

@app.post("/record", status_code=201)
def create_record(data: RecordIn):
    if data.user_id not in users:
        return not_found("User", data.user_id)
    if data.category_id not in categories:
        return not_found("Category", data.category_id)
    created_at = data.created_at or datetime.now(timezone.utc)
    record = {
        "id": next_id("record"),
        "user_id": data.user_id,
        "category_id": data.category_id,
        "created_at": created_at.isoformat(),
        "amount": data.amount,
    }
    records[record["id"]] = record
    return record


@app.get("/record/{record_id}")
def get_record(record_id: int):
    if record_id not in records:
        return not_found("Record", record_id)
    return records[record_id]


@app.delete("/record/{record_id}", status_code=204)
def delete_record(record_id: int):
    if record_id not in records:
        return not_found("Record", record_id)
    del records[record_id]
    return Response(status_code=204)


@app.get("/record")
def get_records(user_id: Optional[int] = None, category_id: Optional[int] = None):
    if user_id is None and category_id is None:
        return error(
            400,
            "invalid_request",
            "At least one query parameter ('user_id' or 'category_id') is required for filtration",
        )
    return [
        r for r in records.values()
        if (user_id is None or r["user_id"] == user_id)
        and (category_id is None or r["category_id"] == category_id)
    ]
