"""Google dork generation for OSINT investigations."""

from __future__ import annotations

from typing import Any

PERSON_DORKS = [
    '"{target}" site:linkedin.com',
    '"{target}" site:facebook.com',
    '"{target}" filetype:pdf',
    '"{target}" site:twitter.com OR site:x.com',
    '"{target}" email OR contact OR "@"',
    '"{target}" resume OR CV OR curriculum vitae',
    '"{target}" site:github.com',
    '"{target}" intext:phone OR intext:telephone',
    '"{target}" site:pastebin.com',
    '"{target}" -site:linkedin.com -site:facebook.com',
]

EMAIL_DORKS = [
    '"{target}"',
    '"{target}" password OR leak OR breach',
    '"{target}" site:pastebin.com',
    '"{target}" site:ghostbin.com OR site:hastebin.com',
    'intext:"{target}"',
    '"{target}" filetype:sql OR filetype:txt OR filetype:csv',
    '"{target}" site:github.com',
]

USERNAME_DORKS = [
    '"{target}" site:twitter.com OR site:x.com',
    '"{target}" site:github.com',
    '"{target}" site:reddit.com',
    '"{target}" site:instagram.com',
    '"{target}" site:tiktok.com',
    '"{target}" site:linkedin.com',
    '"{target}" profile OR account',
    'inurl:"{target}"',
]

DOMAIN_DORKS = [
    'site:{target}',
    'site:{target} filetype:pdf',
    'site:{target} filetype:xls OR filetype:xlsx',
    'site:{target} inurl:admin OR inurl:login OR inurl:panel',
    'site:{target} inurl:api OR inurl:graphql OR inurl:swagger',
    'site:{target} intext:password OR intext:secret OR intext:api_key',
    'site:{target} ext:env OR ext:bak OR ext:config OR ext:cfg',
    'site:{target} inurl:wp-content OR inurl:wordpress',
    '"@{target}" email',
    'related:{target}',
    'link:{target}',
    'cache:{target}',
]

COMPANY_DORKS = [
    '"{target}" site:linkedin.com/in',
    '"{target}" employees OR staff OR team',
    '"{target}" org-chart OR organization',
    '"{target}" filetype:pdf annual report',
    '"{target}" job OR careers OR "we are hiring"',
    '"{target}" breach OR leak OR hack',
    '"{target}" "internal" OR "confidential"',
    'site:glassdoor.com "{target}"',
]


def generate_dorks(target: str, target_type: str) -> dict[str, Any]:
    """Generate targeted Google dork queries."""
    templates_map: dict[str, list[str]] = {
        "person": PERSON_DORKS,
        "email": EMAIL_DORKS,
        "username": USERNAME_DORKS,
        "domain": DOMAIN_DORKS,
        "company": COMPANY_DORKS,
    }

    templates = templates_map.get(target_type, PERSON_DORKS)
    dorks = [t.format(target=target) for t in templates]

    return {
        "status": "ok",
        "target": target,
        "target_type": target_type,
        "dorks": dorks,
        "instructions": (
            "Copy these queries into Google or Bing. "
            "Wrap in site:google.com/search?q=... for direct linking. "
            "Use with caution and respect robots.txt."
        ),
    }
