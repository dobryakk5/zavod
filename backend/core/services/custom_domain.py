from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlsplit

import dns.exception
import dns.resolver


_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$"
)


class CustomDomainValidationError(ValueError):
    pass


@dataclass(slots=True)
class CustomDomainVerificationResult:
    verified: bool
    method: str
    domain: str
    expected_cname: str
    resolved_cname: list[str]
    resolved_ips: list[str]
    error: str | None = None


def normalize_custom_domain(value: object) -> str:
    raw_value = str(value or "").strip().lower()
    if not raw_value:
        raise CustomDomainValidationError("Домен не указан.")

    candidate = raw_value if "://" in raw_value else f"//{raw_value}"
    parsed = urlsplit(candidate)
    host = (parsed.hostname or "").strip().lower().rstrip(".")

    if not host:
        raise CustomDomainValidationError("Не удалось определить хост домена.")

    if not _DOMAIN_RE.match(host):
        raise CustomDomainValidationError("Укажите корректный домен (например, site.example.com).")

    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise CustomDomainValidationError("IP-адрес нельзя использовать как свой домен.")

    return host


def _normalize_edge_ips(values: Iterable[str] | None) -> set[str]:
    normalized: set[str] = set()
    for value in values or []:
        candidate = str(value or "").strip()
        if not candidate:
            continue
        try:
            normalized.add(str(ipaddress.ip_address(candidate)))
        except ValueError:
            continue
    return normalized


def _resolve_cname(domain: str, resolver: dns.resolver.Resolver) -> list[str]:
    try:
        records = resolver.resolve(domain, "CNAME")
        return [str(item.target).rstrip(".").lower() for item in records]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return []


def _resolve_ip_records(domain: str, resolver: dns.resolver.Resolver) -> list[str]:
    resolved: set[str] = set()
    for record_type in ("A", "AAAA"):
        try:
            records = resolver.resolve(domain, record_type)
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
            continue
        for item in records:
            value = str(item).strip()
            if value:
                resolved.add(value)
    return sorted(resolved)


def verify_custom_domain_dns(
    domain: str,
    *,
    expected_cname_target: str,
    edge_ips: Iterable[str] | None = None,
    timeout_seconds: float = 3.0,
) -> CustomDomainVerificationResult:
    normalized_domain = normalize_custom_domain(domain)
    expected_cname = normalize_custom_domain(expected_cname_target)
    expected_edge_ips = _normalize_edge_ips(edge_ips)

    resolver = dns.resolver.Resolver(configure=True)
    resolver.timeout = timeout_seconds
    resolver.lifetime = timeout_seconds

    resolved_cname: list[str] = []
    resolved_ips: list[str] = []

    try:
        resolved_cname = _resolve_cname(normalized_domain, resolver)
        if expected_cname in resolved_cname:
            return CustomDomainVerificationResult(
                verified=True,
                method="cname",
                domain=normalized_domain,
                expected_cname=expected_cname,
                resolved_cname=resolved_cname,
                resolved_ips=[],
            )

        resolved_ips = _resolve_ip_records(normalized_domain, resolver)
        if expected_edge_ips and expected_edge_ips.intersection(resolved_ips):
            return CustomDomainVerificationResult(
                verified=True,
                method="edge_ip",
                domain=normalized_domain,
                expected_cname=expected_cname,
                resolved_cname=resolved_cname,
                resolved_ips=resolved_ips,
            )

        if resolved_cname:
            error = (
                f"CNAME не совпадает с ожидаемым значением {expected_cname}. "
                f"Найдено: {', '.join(resolved_cname)}"
            )
        elif expected_edge_ips:
            error = (
                "DNS записи не совпадают с ожидаемой конфигурацией. "
                "Проверьте CNAME или A/AAAA."
            )
        else:
            error = f"CNAME запись для домена не найдена или не указывает на {expected_cname}."

        return CustomDomainVerificationResult(
            verified=False,
            method="none",
            domain=normalized_domain,
            expected_cname=expected_cname,
            resolved_cname=resolved_cname,
            resolved_ips=resolved_ips,
            error=error,
        )
    except dns.exception.DNSException as exc:
        return CustomDomainVerificationResult(
            verified=False,
            method="none",
            domain=normalized_domain,
            expected_cname=expected_cname,
            resolved_cname=resolved_cname,
            resolved_ips=resolved_ips,
            error=f"DNS ошибка: {exc}",
        )
