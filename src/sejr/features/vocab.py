"""Fixed stack vocabulary. Adding or changing a term means rerunning every month."""

import re
from dataclasses import dataclass

# Short or common words (Go, C, R) only count when they read like an item in a tech
# list: "Python, Go and Rust", "written in C", "Go/Lua", "(mainly Go)".
LIST_BEFORE = re.compile(
    r"(?:[,/(|&+:•*]\s*|\b(?:in|and|or|with|using|of|like|mainly|including|e\.g\.|written"
    r"|write|writing|use|uses|plus|some|also|both|knowledge|experience|stack)\s+)$",
    re.IGNORECASE,
)
LIST_AFTER = re.compile(
    r"^(?:\s*[,/)|&+;]|\s+(?:and|or|&)\s|\.(?:\s|$)|\s*$"
    r"|\s+(?:developers?|engineers?|code|services|microservices|backend|programming|experience)\b)",
    re.IGNORECASE,
)
# "Series B or C", "Plan A, B, C", "Objective C": a letter, not a language.
NOT_A_LANGUAGE = re.compile(
    r"\b(?:series|round|tier|grade|stage|class|type|vitamin|plan|option|section|objective)\b"
    r"|(?-i:\b[AB])\s*(?:,|/|or|and)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Term:
    always: re.Pattern[str] | None  # counts wherever it appears
    in_list: re.Pattern[str] | None  # counts only inside a tech list
    near: re.Pattern[str] | None  # in_list also needs this within 80 characters


def _term(
    always: str | None = None, in_list: str | None = None, near: str | None = None
) -> Term:
    def compile_(pattern: str | None, flags: int = 0) -> re.Pattern[str] | None:
        return re.compile(pattern, flags) if pattern else None

    return Term(compile_(always), compile_(in_list), compile_(near, re.IGNORECASE))


TERMS: dict[str, Term] = {
    "Python": _term(r"(?i:\bpython\b)"),
    "TypeScript": _term(r"(?i:\btypescript\b)"),
    "JavaScript": _term(r"(?i:\bjavascript\b)|\bJS\b"),
    "Go": _term(
        r"(?i:\bgolang\b)",
        in_list=r"(?<![\w.#+\-'’])Go(?![\w#+\-'’]|\s*-?\s*(?i:to|ahead|live|giants|getter)\b)",
    ),
    "Rust": _term(r"\bR(?:ust|UST)\b(?!\s+Belt)|(?i:\brustlang\b)"),
    "Java": _term(r"(?i:\bjava\b)"),
    "Kotlin": _term(r"(?i:\bkotlin\b)"),
    "Swift": _term(r"\bSwift(?:UI)?\b"),
    "C": _term(in_list=r"(?<![\w.#+\-'’])C(?![\w#+\-'’]|\(\+\+\)|\.\w)"),
    "C++": _term(r"(?i:c\+\+|\bcpp\b)|\bC\(\+\+\)"),
    "C#": _term(r"(?<![\w#])C#|(?i:\bc-?sharp\b)"),
    "Ruby": _term(r"(?i:\bruby\b)"),
    "Elixir": _term(r"(?i:\belixir\b)"),
    "Scala": _term(r"(?i:\bscala\b)"),
    "PHP": _term(r"(?i:\bphp\b)"),
    "Haskell": _term(r"(?i:\bhaskell\b)"),
    "R": _term(
        in_list=r"(?<![\w.#+\-&'’])R(?![\w#+\-&'’.])",
        near=r"\b(?:python|sql|stata|sas|julia|matlab|statistic\w*|shiny|tidyverse|spss|pandas)\b",
    ),
    "React": _term(r"\bReact(?:\.?js)?\b|(?i:\breactjs\b)"),
    "Vue": _term(r"(?i:\bvue(?:\.?js)?\b)"),
    "Angular": _term(r"(?i:\bangular(?:\.?js)?\b)"),
    "Next.js": _term(r"(?i:\bnext\.?js\b)"),
    "Node.js": _term(r"(?i:\bnode\.?js\b)|\bNode\b"),
    "Django": _term(r"(?i:\bdjango\b)"),
    "Rails": _term(r"\bRails\b|\bRoR\b"),
    "iOS": _term(r"\biOS\b|\bIOS\b"),
    "Android": _term(r"(?i:\bandroid\b)"),
    "Kubernetes": _term(r"(?i:\bkubernetes\b|\bk8s\b)"),
    "Docker": _term(r"(?i:\bdocker\b)"),
    "AWS": _term(r"\bAWS\b|(?i:\bamazon web services\b)"),
    "GCP": _term(r"\bGCP\b|(?i:\bgoogle cloud\b)"),
    "Azure": _term(r"\bAzure\b"),
    "Terraform": _term(r"(?i:\bterraform\b)"),
    "Postgres": _term(r"(?i:\bpostgres(?:ql)?\b)"),
    "MySQL": _term(r"(?i:\bmysql\b)"),
    "MongoDB": _term(r"(?i:\bmongo(?:db)?\b)"),
    "Redis": _term(r"(?i:\bredis\b)"),
    "Kafka": _term(r"(?i:\bkafka\b)"),
    "Spark": _term(r"\bSpark\b(?!\s+Capital)|(?i:\bpyspark\b)"),
    "GraphQL": _term(r"(?i:\bgraphql\b)"),
    "PyTorch": _term(r"(?i:\bpytorch\b)"),
    "TensorFlow": _term(r"(?i:\btensorflow\b)"),
    "Machine learning": _term(r"(?i:\bmachine learning\b)|\bML\b"),
    "LLM": _term(r"(?i:\bllms?\b|\blarge language models?\b)"),
    "RAG": _term(r"\bRAG\b|(?i:\bretrieval[- ]augmented\b)"),
    "AI agents": _term(
        r"(?i:\b(?:ai|llm|autonomous|coding|software)\s+agents?\b|\bagentic\b|\bmulti-agent\b"
        r"|\bagent\s+(?:frameworks?|orchestration|workflows?|systems?|infrastructure)\b)"
    ),
}


def _in_list(text: str, term: Term, m: re.Match[str]) -> bool:
    before = text[max(0, m.start() - 25) : m.start()]
    after = text[m.end() : m.end() + 25]
    if NOT_A_LANGUAGE.search(before):
        return False
    if term.near and not term.near.search(text[max(0, m.start() - 80) : m.end() + 80]):
        return False
    return bool(LIST_BEFORE.search(before) or LIST_AFTER.search(after))


def _mentions(text: str, term: Term) -> bool:
    if term.always and term.always.search(text):
        return True
    return bool(term.in_list) and any(
        _in_list(text, term, m) for m in term.in_list.finditer(text)
    )


def stack_terms(text: str) -> list[str]:
    return [name for name, term in TERMS.items() if _mentions(text, term)]
