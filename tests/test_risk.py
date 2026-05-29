from prism.diff.source import ChangedFile
from prism.risk import RiskTier, assess_risk_tier, is_security_sensitive


def _files(specs: list[tuple[str, int, int]]) -> list[ChangedFile]:
    return [ChangedFile(path=p, patch="", added=a, removed=r) for p, a, r in specs]


def test_trivial_small_change() -> None:
    assert assess_risk_tier(_files([("a.py", 3, 2)])) is RiskTier.TRIVIAL


def test_lite_moderate_change() -> None:
    assert assess_risk_tier(_files([("a.py", 40, 20)])) is RiskTier.LITE


def test_full_large_change() -> None:
    assert assess_risk_tier(_files([("a.py", 150, 30)])) is RiskTier.FULL


def test_full_when_many_files() -> None:
    many = _files([(f"f{i}.py", 1, 0) for i in range(60)])
    assert assess_risk_tier(many) is RiskTier.FULL


def test_security_sensitive_path_forces_full_even_when_tiny() -> None:
    assert assess_risk_tier(_files([("auth/login.py", 1, 0)])) is RiskTier.FULL
    assert assess_risk_tier(_files([(".github/workflows/ci.yml", 2, 0)])) is RiskTier.FULL
    assert assess_risk_tier(_files([("infra/terraform/main.tf", 1, 0)])) is RiskTier.FULL


def test_is_security_sensitive() -> None:
    assert is_security_sensitive("internal/auth/session.go")
    assert is_security_sensitive("Dockerfile")
    assert not is_security_sensitive("src/util/strings.py")


def test_tier_ordering() -> None:
    assert RiskTier.FULL.rank > RiskTier.LITE.rank > RiskTier.TRIVIAL.rank
