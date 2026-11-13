import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Agent, Post, User
from app.security import create_access_token


@pytest.fixture
def saved_post_api(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'saved_posts.db').as_posix()}"
    test_engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with test_session() as db:
        owner = User(name="Owner", email="owner@example.test", password_hash="unused")
        another_user = User(name="Another", email="another@example.test", password_hash="unused")
        db.add_all([owner, another_user])
        db.flush()
        agent = Agent(user_id=owner.id, name="Owner agent", industry="Food")
        db.add(agent)
        db.flush()
        post = Post(agent_id=agent.id, title="Fresh produce", description="Seeking regional partners.")
        db.add(post)
        db.commit()
        post_id = post.id
        owner_id = owner.id
        owner_token = create_access_token(str(owner.id))
        another_token = create_access_token(str(another_user.id))

    client = TestClient(app)
    try:
        yield client, post_id, owner_id, owner_token, another_token
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()


def test_saved_posts_are_private_and_idempotent(saved_post_api):
    client, post_id, _, owner_token, another_token = saved_post_api
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    another_headers = {"Authorization": f"Bearer {another_token}"}

    first_save = client.post(f"/api/saved-posts/{post_id}", headers=owner_headers)
    repeated_save = client.post(f"/api/saved-posts/{post_id}", headers=owner_headers)
    assert first_save.status_code == 200
    assert repeated_save.status_code == 200

    owner_saved = client.get("/api/saved-posts", headers=owner_headers)
    assert owner_saved.status_code == 200
    assert len(owner_saved.json()) == 1
    assert owner_saved.json()[0]["title"] == "Fresh produce"
    assert owner_saved.json()[0]["business_name"] == "Owner"
    assert client.get("/api/saved-posts", headers=another_headers).json() == []
    assert client.delete(f"/api/saved-posts/{post_id}", headers=another_headers).json()["saved"] is False
    assert len(client.get("/api/saved-posts", headers=owner_headers).json()) == 1

    assert client.delete(f"/api/saved-posts/{post_id}", headers=owner_headers).json()["saved"] is False
    assert client.delete(f"/api/saved-posts/{post_id}", headers=owner_headers).json()["saved"] is False
    assert client.get("/api/saved-posts", headers=owner_headers).json() == []
    assert client.post("/api/saved-posts/9999", headers=owner_headers).status_code == 404
    assert client.get("/api/saved-posts").status_code == 403


def test_public_post_identifies_owner_for_connection_requests(saved_post_api):
    client, _, owner_id, _, sender_token = saved_post_api
    sender_headers = {"Authorization": f"Bearer {sender_token}"}

    posts = client.get("/api/posts").json()
    assert len(posts) == 1
    assert posts[0]["user_id"] == owner_id

    response = client.post(
        "/api/connections",
        headers=sender_headers,
        json={
            "receiver_id": posts[0]["user_id"],
            "note": f"Interested in your update: {posts[0]['title']}",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_post_lifecycle_is_owner_only_and_cleans_saved_references(saved_post_api):
    client, post_id, _, owner_token, another_token = saved_post_api
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    another_headers = {"Authorization": f"Bearer {another_token}"}
    update = {
        "title": "Updated produce opportunity",
        "description": "Seeking a reliable regional distributor.",
        "category": "Partnership",
        "requirements": "Cold-chain delivery",
    }

    assert client.post(f"/api/saved-posts/{post_id}", headers=another_headers).status_code == 200
    assert client.put(f"/api/posts/{post_id}", headers=another_headers, json=update).status_code == 404
    assert client.delete(f"/api/posts/{post_id}", headers=another_headers).status_code == 404

    response = client.put(f"/api/posts/{post_id}", headers=owner_headers, json=update)
    assert response.status_code == 200
    assert response.json()["title"] == update["title"]
    assert client.get("/api/posts").json()[0]["description"] == update["description"]
    assert client.get("/api/saved-posts", headers=another_headers).json()[0]["title"] == update["title"]
    assert client.put(
        f"/api/posts/{post_id}",
        headers=owner_headers,
        json={**update, "title": "   "},
    ).status_code == 422
    assert client.put(
        f"/api/posts/{post_id}",
        headers=owner_headers,
        json={**update, "description": "x" * 5001},
    ).status_code == 422

    response = client.delete(f"/api/posts/{post_id}", headers=owner_headers)
    assert response.status_code == 200
    assert response.json() == {"post_id": post_id, "deleted": True}
    assert client.get("/api/posts").json() == []
    assert client.get("/api/saved-posts", headers=another_headers).json() == []
    assert client.delete(f"/api/posts/{post_id}", headers=owner_headers).status_code == 404


def test_invalid_token_subject_returns_unauthorized(saved_post_api):
    client, _, _, _, _ = saved_post_api
    token = create_access_token("not-a-user-id")

    response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid user identifier in token"


def test_registration_enforces_password_length_and_bcrypt_byte_limit(saved_post_api):
    client, _, _, _, _ = saved_post_api
    for index, password in enumerate(("shortpass", "🧡" * 19)):
        response = client.post(
            "/api/register",
            json={
                "name": f"New User {index}",
                "email": f"new-user-{index}@example.test",
                "password": password,
            },
        )
        assert response.status_code == 422
