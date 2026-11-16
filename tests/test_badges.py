"""未读角标：别人发来的未读私信才算；自己发的、已读的、和拉黑对象之间的都不算。"""
from app.models import DmMessage, DmThread, User, utcnow
from tests.test_h5_domain import headers, register


def test_badge_counts_unread_messages_across_threads_and_skips_blocked(client):
    me = register(client, "me-badge@example.com")
    register(client, "friend-badge@example.com")
    register(client, "pest-badge@example.com")
    session = client.session_factory()
    ids = {u.email.split("-")[0]: u.id for u in session.query(User)}
    for other, unread in (("friend", 2), ("pest", 1)):
        low, high = sorted((ids["me"], ids[other]))
        thread = DmThread(user_low=low, user_high=high, status="active")
        session.add(thread)
        session.flush()
        session.add_all(DmMessage(thread_id=thread.id, sender_id=ids[other], body="在吗") for _ in range(unread))
        session.add(DmMessage(thread_id=thread.id, sender_id=ids[other], body="旧的", read_at=utcnow()))
        session.add(DmMessage(thread_id=thread.id, sender_id=ids["me"], body="我发的"))
    session.commit()
    session.close()

    assert client.get("/api/v1/me/badges", headers=headers(me)).json()["messages"] == 3
    assert client.put(f"/api/v1/me/blocks/{ids['pest']}", headers=headers(me)).status_code == 200
    assert client.get("/api/v1/me/badges", headers=headers(me)).json()["messages"] == 2
