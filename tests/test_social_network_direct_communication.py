import asyncio

import pytest

hypernetx = pytest.importorskip("hypernetx")

from src.environment.social_network import SocialNetwork


class _StubResident:
    def __init__(self, resident_id: int):
        self.resident_id = resident_id
        self.received = []

    async def receive_information(self, message_content: str):
        self.received.append(message_content)
        return (f"ack:{message_content}", "friend")


def test_communicate_resident_to_resident_increments_dialogue_count():
    sn = SocialNetwork()
    sn.residents = {
        1: _StubResident(1),
        2: _StubResident(2),
    }

    resp = asyncio.run(sn.communicate_resident_to_resident(1, 2, "hi"))
    assert resp == ("ack:hi", "friend")
    assert sn.dialogue_count == 1
    assert sn.residents[2].received == ["hi"]


def test_communicate_resident_to_residents_returns_mapping_and_limits():
    sn = SocialNetwork()
    sn.residents = {
        1: _StubResident(1),
        2: _StubResident(2),
        3: _StubResident(3),
    }

    sn.MAX_DIALOGUES_PER_STEP = 1
    sn.reset_dialogue_count()

    result = asyncio.run(sn.communicate_resident_to_residents(1, [2, 3], "hello"))
    assert set(result.keys()) == {2, 3}

    # 由于对话额度只有1，只会投递给列表中的第一个可达接收者
    assert result[2] == ("ack:hello", "friend")
    assert result[3] is None
    assert sn.dialogue_count == 1


def test_communicate_user_to_resident_proxies_to_direct_send():
    sn = SocialNetwork()
    sn.residents = {10: _StubResident(10)}

    resp = asyncio.run(sn.communicate_user_to_resident("u1", 10, "from user"))
    assert resp == ("ack:from user", "friend")
    assert sn.residents[10].received == ["from user"]
