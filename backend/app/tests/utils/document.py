import itertools as it
import functools as ft
from uuid import UUID
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from urllib.parse import ParseResult, urlunparse

import pytest
from httpx import Response
from sqlmodel import Session, delete
from fastapi.testclient import TestClient

from app.core.config import settings
from app.crud.user import get_user_by_email
from app.models import Document
from app.utils import APIResponse


@ft.cache
def get_user_id_by_email(db: Session):
    user = get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    return user.id


def httpx_to_standard(response: Response):
    return APIResponse(**response.json())


class DocumentIndexGenerator:
    def __init__(self, start=0):
        self.start = start

    def __iter__(self):
        return self

    def __next__(self):
        uu_id = self.peek()
        self.start += 1
        return uu_id

    def peek(self):
        return self.start


class DocumentMaker:
    def __init__(self, db: Session):
        self.owner_id = get_user_id_by_email(db)
        self.index = DocumentIndexGenerator()

    def __iter__(self):
        return self

    def __next__(self):
        doc_id = next(self.index)
        fname = Path(f"/{doc_id}").with_suffix(".xyz")

        return Document(
            id=doc_id,
            owner_id=self.owner_id,
            fname=fname.name,
            object_store_url=fname.as_uri(),
        )


class DocumentStore:
    @staticmethod
    def clear(db: Session):
        db.exec(delete(Document))
        db.commit()

    @property
    def owner(self):
        return self.documents.owner_id

    def __init__(self, db: Session):
        self.db = db
        self.documents = DocumentMaker(self.db)
        self.clear(self.db)

    def put(self):
        doc = next(self.documents)

        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        return doc

    def extend(self, n: int):
        for _ in range(n):
            yield self.put()

    def fill(self, n: int):
        return list(self.extend(n))


class Route:
    _empty = ParseResult(*it.repeat("", len(ParseResult._fields)))
    _root = Path(settings.API_V1_STR, "documents")

    def __init__(self, endpoint, **qs_args):
        self.endpoint = endpoint
        self.qs_args = qs_args

    def __str__(self):
        return urlunparse(self.to_url())

    def to_url(self):
        path = self._root.joinpath(self.endpoint)
        kwargs = {
            "path": str(path),
        }
        if self.qs_args:
            query = "&".join(it.starmap("{}={}".format, self.qs_args.items()))
            kwargs["query"] = query

        return self._empty._replace(**kwargs)

    def append(self, doc: Document):
        endpoint = Path(self.endpoint, doc.id)
        return type(self)(endpoint, **self.qs_args)


@dataclass
class WebCrawler:
    client: TestClient
    superuser_token_headers: dict[str, str]

    def get(self, route: Route):
        return self.client.get(
            str(route),
            headers=self.superuser_token_headers,
        )


class DocumentComparator:
    @ft.singledispatchmethod
    @staticmethod
    def to_string(value):
        return value

    @to_string.register
    @staticmethod
    def _(value: int):
        return str(value)

    @to_string.register
    @staticmethod
    def _(value: datetime):
        return value.isoformat()

    def __init__(self, document: Document):
        self.document = document

    def __eq__(self, other: dict):
        this = dict(self.to_dict())
        return this == other

    def to_dict(self):
        document = dict(self.document)
        for k, v in document.items():
            yield (k, self.to_string(v))


@pytest.fixture
def crawler(client: TestClient, superuser_token_headers: dict[str, str]):
    return WebCrawler(client, superuser_token_headers)
