"""Deterministic task context parser: tokenization, stopword removal, and domain inference."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Set

from agentproof.core.models import TaskContext

# Common English stopwords and generic verbs to filter out
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves",
    # Generic action verbs
    "fix", "fixes", "fixed", "update", "updates", "updated", "add", "adds", "added",
    "change", "changes", "changed", "make", "makes", "made", "implement", "implements",
    "implemented", "modify", "modifies", "modified", "refactor", "support", "handling",
}

# Domain keyword associations
DOMAIN_KEYWORDS = {
    "auth": {"auth", "authentication", "token", "tokens", "session", "sessions", "jwt", "login", "password", "oauth", "credential", "credentials", "permission", "rbac"},
    "database": {"db", "database", "migration", "migrations", "sql", "model", "models", "schema", "table", "tables", "entity", "orm", "postgres", "sqlite", "alembic"},
    "api": {"api", "endpoint", "endpoints", "rest", "route", "routes", "http", "controller", "handler", "request", "response"},
    "cli": {"cli", "command", "commands", "flag", "flags", "argument", "arguments", "parser", "terminal", "subcommand"},
    "ui": {"ui", "frontend", "css", "theme", "html", "react", "component", "components", "page", "pages", "style", "styles"},
    "deployment": {"docker", "compose", "ci", "workflow", "workflows", "deploy", "deployment", "kubernetes", "k8s", "container", "action", "actions"},
    "config": {"config", "configuration", "env", "settings", "options", "preferences"},
    "testing": {"test", "tests", "testing", "spec", "fixture", "mock"},
}

PATH_REGEX = re.compile(r"\b([A-Za-z0-9_\-\./\\]+\.[a-zA-Z0-9]+)\b")
SYMBOL_REGEX = re.compile(r"\b([A-Z][a-zA-Z0-9]+|[a-z]+_[a-z0-9_]+)\b")


class TaskParser:
    """Parses raw task instructions into structured TaskContext."""

    def parse(self, text: str) -> TaskContext:
        """Parse raw task text into a TaskContext."""
        if not text or not text.strip():
            return TaskContext(
                raw_text="",
                normalized_keywords=[],
                referenced_paths=[],
                referenced_symbols=[],
                expected_domains=[],
                inferred_scope="UNKNOWN",
                confidence="LOW",
            )

        clean_text = text.strip()

        # 1. Extract referenced paths
        raw_paths = PATH_REGEX.findall(clean_text)
        referenced_paths = [p.replace("\\", "/") for p in raw_paths if "/" in p or "\\" in p or p.endswith((".py", ".ts", ".js", ".json", ".yml", ".yaml", ".toml"))]

        # 2. Extract referenced symbols
        raw_symbols = SYMBOL_REGEX.findall(clean_text)
        referenced_symbols = [s for s in raw_symbols if s.lower() not in STOPWORDS and len(s) > 2]

        # 3. Normalize keywords
        tokens = re.findall(r"\b[A-Za-z0-9_\-]+\b", clean_text.lower())
        keywords = [t for t in tokens if t not in STOPWORDS and len(t) > 2 and not t.isdigit()]
        # Preserve order while deduplicating
        seen_kw: Set[str] = set()
        dedup_keywords: List[str] = []
        for kw in keywords:
            if kw not in seen_kw:
                seen_kw.add(kw)
                dedup_keywords.append(kw)

        # 4. Infer expected domains
        expected_domains: List[str] = []
        for domain, domain_tokens in DOMAIN_KEYWORDS.items():
            if any(t in domain_tokens for t in tokens) or any(t in domain_tokens for t in dedup_keywords):
                expected_domains.append(domain)

        # 5. Inferred scope
        if referenced_paths:
            inferred_scope = "NARROW"
        elif len(expected_domains) == 1 and len(dedup_keywords) <= 3:
            inferred_scope = "NARROW"
        elif len(expected_domains) > 2 or len(dedup_keywords) > 6:
            inferred_scope = "BROAD"
        else:
            inferred_scope = "MEDIUM"

        # 6. Confidence rating
        if referenced_paths or len(expected_domains) >= 1:
            confidence = "HIGH"
        elif len(dedup_keywords) >= 2:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return TaskContext(
            raw_text=clean_text,
            normalized_keywords=dedup_keywords,
            referenced_paths=referenced_paths,
            referenced_symbols=referenced_symbols,
            expected_domains=expected_domains,
            inferred_scope=inferred_scope,
            confidence=confidence,
        )

    def parse_file(self, file_path: str | Path) -> TaskContext:
        """Parse task text from a file on disk."""
        path = Path(file_path)
        if not path.is_file():
            return self.parse("")
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            return self.parse(content)
        except Exception:
            return self.parse("")
