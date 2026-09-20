import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJ_DATABASE_URL", "sqlite:///./test_global.db")
os.environ.setdefault("DJ_ARTIFACT_STORAGE_DIR", "./test_artifact_store")
os.environ.setdefault("DJ_AI_PROVIDER", "mock")

import shutil

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.domain.models  # noqa: F401
from app.db import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def clean_storage():
    yield
    shutil.rmtree("./test_artifact_store", ignore_errors=True)


@pytest.fixture()
def case(db):
    from app.domain.enums import CaseStatus
    from app.domain.models import Case, User, public_id
    user = User(public_id=public_id("USR"))
    db.add(user)
    db.flush()
    c = Case(public_id=public_id("CASE"), user_id=user.id, status=CaseStatus.CREATED,
             question_text="آیا دندان 46 باید عصب‌کشی شود؟",
             dentist_recommendation_text="دکتر گفت عصب کشی و روکش لازم است")
    db.add(c)
    db.flush()
    return c


@pytest.fixture()
def pdf_bytes():
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Treatment Plan\nTooth 46: RCT\nCrown\nInvoice total: 5,000,000 toman")
    data = doc.tobytes()
    doc.close()
    return data
