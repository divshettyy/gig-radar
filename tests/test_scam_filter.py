import pytest
from classify import keep, is_scammy


@pytest.mark.parametrize("title,desc", [
    ("Data Entry Clerk", "Pay a registration fee to start; earn $200 per day from home"),
    ("Brand Ambassador", "100% commission, build your downline"),
    ("Virtual Assistant", "Commission-only role, unlimited potential"),
    ("Trader", "Join our forex signals telegram"),
    ("Payment Processor", "We will send you a check; cash a check and wire the rest"),
    ("Online Rep", "Guaranteed income of $5000/week"),
    ("Assistant", "Purchase your own starter kit before you begin"),
])
def test_scams_are_dropped(title, desc):
    assert is_scammy(title, desc)
    assert keep(title, [], desc, "Remote", "RemoteOK") is False


@pytest.mark.parametrize("title,desc", [
    ("Backend Developer, Crypto Exchange", "Build APIs in Python for a regulated exchange."),
    ("Sales Engineer", "Base salary plus commission, remote."),
    ("Technical Writer", "Write docs for our payments API. Gift card integrations a plus."[:40]),
    ("Python Developer", "Remote, team of 10, security deposit module for a rental app"[:30]),
    ("Content Writer", "Marketing blog posts about network security."),
])
def test_legit_gigs_are_kept(title, desc):
    assert not is_scammy(title, desc)
    assert keep(title, [], desc, "Remote", "RemoteOK") is True
