from __future__ import annotations

from core.services import custom_domain


def test_normalize_custom_domain_strips_scheme_path_port():
    normalized = custom_domain.normalize_custom_domain("https://WWW.Example.com:443/path?q=1")
    assert normalized == "www.example.com"


def test_verify_custom_domain_dns_uses_cname(monkeypatch):
    monkeypatch.setattr(custom_domain, "_resolve_cname", lambda domain, resolver: ["fibonatty.ru"])
    monkeypatch.setattr(custom_domain, "_resolve_ip_records", lambda domain, resolver: [])

    result = custom_domain.verify_custom_domain_dns(
        "www.client-site.com",
        expected_cname_target="fibonatty.ru",
        edge_ips=["1.2.3.4"],
    )

    assert result.verified is True
    assert result.method == "cname"
    assert result.error is None


def test_verify_custom_domain_dns_uses_edge_ip_fallback(monkeypatch):
    monkeypatch.setattr(custom_domain, "_resolve_cname", lambda domain, resolver: [])
    monkeypatch.setattr(custom_domain, "_resolve_ip_records", lambda domain, resolver: ["1.2.3.4"])

    result = custom_domain.verify_custom_domain_dns(
        "client-site.com",
        expected_cname_target="fibonatty.ru",
        edge_ips=["1.2.3.4"],
    )

    assert result.verified is True
    assert result.method == "edge_ip"
    assert result.error is None


def test_verify_custom_domain_dns_returns_error_on_mismatch(monkeypatch):
    monkeypatch.setattr(custom_domain, "_resolve_cname", lambda domain, resolver: ["other.example.com"])
    monkeypatch.setattr(custom_domain, "_resolve_ip_records", lambda domain, resolver: ["8.8.8.8"])

    result = custom_domain.verify_custom_domain_dns(
        "www.client-site.com",
        expected_cname_target="fibonatty.ru",
        edge_ips=["1.2.3.4"],
    )

    assert result.verified is False
    assert result.method == "none"
    assert result.error is not None
