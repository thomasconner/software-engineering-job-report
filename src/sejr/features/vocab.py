"""Fixed stack vocabulary. Adding or changing a term means rerunning every month."""

import re
from dataclasses import dataclass

from sejr.features.company import company_name
from sejr.features.tokens import header_line

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
CONTEXT_CHARS = 80
# A product that is also a company ("Datadog", "Snowflake") is often named as an investor,
# a customer, an acquirer or a former employer rather than as a tool. These cues, a few
# words before the name in the same sentence, mean the name is the company.
COMPANY_CUE = re.compile(
    r"\b(?:ex|former(?:ly)?|alumni|alums?|acquired|acquisition|invest(?:ed|ors?|ment)"
    r"|funded|customers?|partners?|partnered|used by|trusted by|brands?|founders?"
    r"|veterans?|worked at|(?:comes?|came|coming) from|engineers from|folks from|people from"
    r"|leaders from|researchers|companies like|teams at|team at|like at|(?:co-?)?founded|sold|raised)\b",
    re.IGNORECASE,
)
CUE_WORDS = 6
# These name the company even in a sentence that lists tools ("used by OpenAI and Datadog").
STRONG_CUE = re.compile(
    r"\b(?:used\s+by|trusted\s+by|companies\s+like|teams?\s+at|customers?)\b",
    re.IGNORECASE,
)
# "backed by" is a cue only next to money: "backed by a MySQL database" is a stack.
BACKED_BY = re.compile(r"\bbacked\s+by\b", re.IGNORECASE)
INVESTOR_WORDS = re.compile(
    r"\b(?:vcs?|venture|ventures|investors?|funding|funded|series\s+[a-f]|raised|seed|capital"
    r"|angels?|a16z|y\s?combinator|yc)\b",
    re.IGNORECASE,
)
# A sentence that lists tools is a stack, whatever cue words it holds ("coming from SaaS tools").
TECH_LIST = re.compile(
    r"\b(?:stack|tech|tools?|tooling|uses?|using|used|built\s+(?:with|on)|powered\s+by|runs?\s+on"
    r"|running\s+on|deploy\w*\s+(?:on|to)|integrat\w*|languages?|frameworks?|databases?)\b",
    re.IGNORECASE,
)
# "Cloudflare CEO", "OpenAI alumni".
COMPANY_AFTER = re.compile(
    r"^(?:'s|’s)?\s+(?:CEO|CTO|COO|founders?|co-?founders?|alumni|alums|veterans|executives?"
    r"|leaders?|leadership|investors?|employees|ventures|fund|researchers|engineers\s+(?:and|&))\b",
    re.IGNORECASE,
)
# "building Vercel for AI": an analogy, not a tool.
ANALOGY_BEFORE = re.compile(
    r"\b(?:building|build|be|becoming|become|the|an?|like)\s+[\"“']?$", re.IGNORECASE
)
ANALOGY_AFTER = re.compile(r"^[\"”']?\s+for\b", re.IGNORECASE)
SENTENCE_END = re.compile(r"[.!?]\s|\n")


@dataclass(frozen=True)
class Term:
    group: str
    always: re.Pattern[str] | None  # counts wherever it appears
    in_list: re.Pattern[str] | None  # counts only inside a tech list
    near: re.Pattern[str] | None  # every match needs this within CONTEXT_CHARS
    # A match is dropped when this is within 30 characters of it.
    exclude: re.Pattern[str] | None
    company: str | None  # the term is also a company (normalized name, see company.py)


def _term(
    group: str,
    always: str | None = None,
    in_list: str | None = None,
    near: str | None = None,
    exclude: str | None = None,
    company: str | None = None,
) -> Term:
    def compile_(pattern: str | None, flags: int = 0) -> re.Pattern[str] | None:
        return re.compile(pattern, flags) if pattern else None

    return Term(
        group,
        compile_(always),
        compile_(in_list),
        compile_(near, re.IGNORECASE),
        compile_(exclude, re.IGNORECASE),
        company,
    )


GROUPS = (
    "language",
    "framework",
    "database",
    "cloud_devops",
    "data",
    "ai_ml",
    "mobile",
)
LANG, FW, DB, OPS, DATA, AI, MOBILE = GROUPS

STATS_NEAR = r"\b(?:python|sql|stata|sas|julia|matlab|statistic\w*|shiny|tidyverse|spss|pandas)\b"
JVM_NEAR = (
    r"\b(?:java|kotlin|jvm|hibernate|maven|gradle|microservices|scala|backend|boot)\b"
)
NODE_NEAR = r"\b(?:node(?:\.?js)?|javascript|typescript|js|ts|mongo\w*|react|api|backend|koa|nest)\b"
OPS_NEAR = (
    r"\b(?:ci|cd|ci/cd|pipelines?|builds?|deploy\w*|docker|git\w*|ansible|puppet|chef|salt\w*"
    r"|devops|kubernetes|k8s|terraform|aws|config\w*|infrastructure|automation|linux|servers?"
    r"|helm|charts?|argo\w*|monitoring|metrics|observability|grafana|prometheus|alert\w*|consul"
    r"|vault|hashicorp|nomad|orchestrat\w*|schedul\w*|jenkins|travis|circleci|sre|cookbooks?)\b"
)
DATA_NEAR = (
    r"\b(?:sql|snowflake|bigquery|redshift|airflow|dagster|warehouse|analytics|databricks"
    r"|looker|fivetran|data|etl|elt|postgres\w*|python)\b"
)
ML_NEAR = (
    r"\b(?:python|pytorch|tensorflow|ml|machine learning|numpy|gpus?|tpus?|deep learning|flax"
    r"|xla|models?|training|research)\b"
)

# The features-3 vocabulary, unchanged so its history does not move.
FEATURES_3_TERMS: dict[str, Term] = {
    "Python": _term(LANG, r"(?i:\bpython\b)"),
    "TypeScript": _term(LANG, r"(?i:\btypescript\b)"),
    "JavaScript": _term(LANG, r"(?i:\bjavascript\b)|\bJS\b"),
    "Go": _term(
        LANG,
        r"(?i:\bgolang\b)",
        in_list=r"(?<![\w.#+\-'’])Go(?![\w#+\-'’]|\s*-?\s*(?i:to|ahead|live|giants|getter)\b)",
    ),
    "Rust": _term(LANG, r"\bR(?:ust|UST)\b(?!\s+Belt)|(?i:\brustlang\b)"),
    "Java": _term(LANG, r"(?i:\bjava\b)"),
    "Kotlin": _term(LANG, r"(?i:\bkotlin\b)"),
    "Swift": _term(LANG, r"\bSwift(?:UI)?\b"),
    "C": _term(LANG, in_list=r"(?<![\w.#+\-'’])C(?![\w#+\-'’]|\(\+\+\)|\.\w)"),
    "C++": _term(LANG, r"(?i:c\+\+|\bcpp\b)|\bC\(\+\+\)"),
    "C#": _term(LANG, r"(?<![\w#])C#|(?i:\bc-?sharp\b)"),
    "Ruby": _term(LANG, r"(?i:\bruby\b)"),
    "Elixir": _term(LANG, r"(?i:\belixir\b)"),
    "Scala": _term(LANG, r"(?i:\bscala\b)"),
    "PHP": _term(LANG, r"(?i:\bphp\b)"),
    "Haskell": _term(LANG, r"(?i:\bhaskell\b)"),
    "R": _term(LANG, in_list=r"(?<![\w.#+\-&'’])R(?![\w#+\-&'’.])", near=STATS_NEAR),
    "React": _term(FW, r"\bReact(?:\.?js)?\b|(?i:\breactjs\b)"),
    "Vue": _term(FW, r"(?i:\bvue(?:\.?js)?\b)"),
    "Angular": _term(FW, r"(?i:\bangular(?:\.?js)?\b)"),
    "Next.js": _term(FW, r"(?i:\bnext\.?js\b)"),
    "Node.js": _term(FW, r"(?i:\bnode\.?js\b)|\bNode\b"),
    "Django": _term(FW, r"(?i:\bdjango\b)"),
    "Rails": _term(FW, r"\bRails\b|\bRoR\b"),
    "iOS": _term(MOBILE, r"\biOS\b|\bIOS\b"),
    "Android": _term(MOBILE, r"(?i:\bandroid\b)"),
    "Kubernetes": _term(OPS, r"(?i:\bkubernetes\b|\bk8s\b)"),
    "Docker": _term(OPS, r"(?i:\bdocker\b)"),
    "AWS": _term(OPS, r"\bAWS\b|(?i:\bamazon web services\b)"),
    "GCP": _term(OPS, r"\bGCP\b|(?i:\bgoogle cloud\b)"),
    "Azure": _term(OPS, r"\bAzure\b"),
    "Terraform": _term(OPS, r"(?i:\bterraform\b)"),
    "Postgres": _term(DB, r"(?i:\bpostgres(?:ql)?\b)"),
    "MySQL": _term(DB, r"(?i:\bmysql\b)"),
    "MongoDB": _term(DB, r"(?i:\bmongo(?:db)?\b)"),
    "Redis": _term(DB, r"(?i:\bredis\b)"),
    "Kafka": _term(DATA, r"(?i:\bkafka\b)"),
    "Spark": _term(DATA, r"\bSpark\b(?!\s+Capital)|(?i:\bpyspark\b)"),
    "GraphQL": _term(FW, r"(?i:\bgraphql\b)"),
    "PyTorch": _term(AI, r"(?i:\bpytorch\b)"),
    "TensorFlow": _term(AI, r"(?i:\btensorflow\b)"),
    "Machine learning": _term(AI, r"(?i:\bmachine learning\b)|\bML\b"),
    "LLM": _term(AI, r"(?i:\bllms?\b|\blarge language models?\b)"),
    "RAG": _term(AI, r"\bRAG\b|(?i:\bretrieval[- ]augmented\b)"),
    "AI agents": _term(
        AI,
        r"(?i:\b(?:ai|llm|autonomous|coding|software)\s+agents?\b|\bagentic\b|\bmulti-agent\b"
        r"|\bagent\s+(?:frameworks?|orchestration|workflows?|systems?|infrastructure)\b)",
    ),
}
# Added in features-4. These never count inside the header's company field ("Green Chef |
# Software Engineer").
ADDED_TERMS: dict[str, Term] = {
    "Clojure": _term(LANG, r"(?i:\bclojure(?:script)?\b|\bcljs\b)"),
    "Erlang": _term(LANG, r"(?i:\berlang\b)"),
    "Perl": _term(LANG, r"(?i:\bperl\b)"),
    "Lua": _term(LANG, r"\bLua(?:JIT)?\b|\bLUA\b"),
    # A first name too: only in a tech list next to another technical word.
    "Julia": _term(
        LANG,
        r"(?i:\bjulialang\b|\bjulia\s+(?:language|programming))",
        in_list=r"\bJulia\b(?!\s*@)",
        near=r"\b(?:python|matlab|fortran|numpy|scientific|numerical|programming|languages?|c\+\+"
        r"|rust|r|sciml|hpc|simulation|sql|go|haskell|java|cuda|fpga)\b",
    ),
    "Dart": _term(LANG, r"\bDart\b(?![-–])"),
    "Zig": _term(LANG, r"\bZig\b(?![-–])"),
    "Objective-C": _term(LANG, r"(?i:\bobj(?:ective)?[- ]?c\b(?!\+\+)|\bobjc\b)"),
    "OCaml": _term(LANG, r"(?i:\bocaml\b)"),
    "F#": _term(LANG, r"(?<![\w#])F#(?!\s*(?:major|minor)\b)|(?i:\bfsharp\b)"),
    # "Solidity" is also an English word ("financial solidity").
    "Solidity": _term(
        LANG,
        r"\bSolidity\b",
        near=r"\b(?:ethereum|smart contracts?|evm|web3|blockchains?|crypto\w*|defi|nfts?|tokens?"
        r"|chains?|dapps?|vyper|rust|typescript|go|javascript|engineers?|developers?|foundry"
        r"|hardhat|on-chain|onchain)\b",
    ),
    # Not MySQL, PostgreSQL or NoSQL: those have no word boundary before "SQL".
    "SQL": _term(LANG, r"(?i:\bsql\b)"),
    "Svelte": _term(FW, r"(?i:\bsvelte(?:kit)?\b)"),
    "FastAPI": _term(FW, r"(?i:\bfastapi\b)"),
    "Flask": _term(FW, r"\bFlask\b"),
    # Also a season ("Spring 2024 internships") and a company name.
    "Spring": _term(
        FW,
        r"\bSpring(?:[- ]?Boot|\s+(?:Framework|MVC|Cloud|Data|Security|Batch|WebFlux))\b",
        in_list=r"\bSpring\b",
        near=JVM_NEAR,
        exclude=r"\bSpring\s*(?:'?\d{2,4}|semester|break|summer|term|quarter|internships?)"
        r"|(?:summer|fall|autumn|winter|this|next|in the|early|late|by)\s*(?:,|/|or|and)?\s*Spring\b"
        r"|\bSpring\s*(?:,|/|or|and|&)\s*(?:summer|fall|autumn|winter)\b",
    ),
    ".NET": _term(FW, r"(?<![\w.])\.N(?:ET|et)\b|\bASP\.NET\b|(?i:\bdotnet\b)"),
    "Laravel": _term(FW, r"(?i:\blaravel\b)"),
    # Also an English word and part of company names ("Panda Express").
    "Express": _term(
        FW,
        r"(?i:\bexpress(?:\.js|js)\b)",
        in_list=r"\bExpress\b",
        near=NODE_NEAR,
        exclude=r"(?:American|Google|Panda|FedEx|Federal|Orient|Pony|Amazon|Ali|Aliexpress"
        r"|Microsoft|SQL\s*Server)\s+Express\b|\bExpress\s+(?:Scripts|Entry|interest)\b",
    ),
    "Tailwind": _term(FW, r"\bTailwind(?:\s*CSS|CSS)?\b|(?i:\btailwindcss\b)"),
    "Flutter": _term(MOBILE, r"\bFlutter\b"),
    "React Native": _term(MOBILE, r"(?i:\breact[- ]?native\b)"),
    "SQLite": _term(DB, r"(?i:\bsqlite3?\b)"),
    "DynamoDB": _term(DB, r"(?i:\bdynamo\s?db\b)"),
    # Also a first name.
    "Cassandra": _term(
        DB,
        r"(?i:\bapache cassandra\b)",
        in_list=r"\bCassandra\b",
        near=r"\b(?:databases?|nosql|kafka|spark|postgres\w*|mysql|redis|mongo\w*|hbase|scylla\w*"
        r"|db|hadoop|elastic\w*|storage|riak|zookeeper|java|scala|python|go)\b",
    ),
    "Elasticsearch": _term(
        DB, r"(?i:\belastic\s?search\b|\bopensearch\b)|\bELK\b", company="elastic"
    ),
    "ClickHouse": _term(DB, r"(?i:\bclickhouse\b)", company="clickhouse"),
    # The tool is capitalized; "snowflake" in lower case is IDs or the insult.
    "Snowflake": _term(DB, r"\bSnowflake\b(?!\s+(?:IDs?|schema))", company="snowflake"),
    "BigQuery": _term(DB, r"(?i:\bbig\s?query\b)"),
    "Redshift": _term(DB, r"(?i:\bredshift\b)"),
    "Supabase": _term(DB, r"(?i:\bsupabase\b)", company="supabase"),
    "Firebase": _term(DB, r"(?i:\bfirebase\b|\bfirestore\b)", company="firebase"),
    "Neo4j": _term(DB, r"(?i:\bneo4j\b)", company="neo4j"),
    "Vector databases": _term(
        DB,
        r"(?i:\bpgvector\b|\bvector\s+(?:databases?|dbs?|stores?|search)\b|\bpinecone\b|\bweaviate\b"
        r"|\bqdrant\b|\bmilvus\b|\bchromadb\b|\blancedb\b|\bturbopuffer\b)",
    ),
    "Jenkins": _term(OPS, r"\bJenkins\b", near=OPS_NEAR),
    "GitHub Actions": _term(OPS, r"(?i:\bgithub\s+actions\b)"),
    "CircleCI": _term(OPS, r"(?i:\bcircle\s?ci\b)", company="circleci"),
    "GitLab CI": _term(
        OPS, r"(?i:\bgitlab[- ]?ci\b|\bgitlab\s+(?:ci/cd|pipelines?)\b)"
    ),
    "Ansible": _term(OPS, r"(?i:\bansible\b)"),
    # Chef, Puppet, Helm and Nomad are also English words; they need ops words nearby.
    "Chef": _term(
        OPS,
        r"\bChef\b(?!'s)",
        near=OPS_NEAR,
        exclude=r"\bChef\s+(?:Robotics|Software|Inc|Labs)\b|\b(?:Green|Home|Blue|Private|Head|Sous"
        r"|Executive|Personal|Pastry|Line)\s+Chef\b",
    ),
    "Puppet": _term(OPS, r"\bPuppet\b", near=OPS_NEAR),
    "Helm": _term(OPS, r"\bHelm\b", near=OPS_NEAR),
    "ArgoCD": _term(OPS, r"(?i:\bargo\s?cd\b|\bargo\s+(?:workflows|rollouts)\b)"),
    "Datadog": _term(OPS, r"(?i:\bdatadog\b)", company="datadog"),
    "Prometheus": _term(OPS, r"\bPrometheus\b", near=OPS_NEAR),
    "Grafana": _term(OPS, r"(?i:\bgrafana\b)", company="grafana"),
    "Pulumi": _term(OPS, r"(?i:\bpulumi\b)", company="pulumi"),
    "Nomad": _term(OPS, r"\bNomad\b", near=OPS_NEAR),
    "Vercel": _term(OPS, r"(?i:\bvercel\b)", company="vercel"),
    # Workers, Pages and the CDN alike: as a platform, not the company.
    "Cloudflare": _term(OPS, r"(?i:\bcloudflare\b)", company="cloudflare"),
    "Linux": _term(OPS, r"(?i:\blinux\b)"),
    "Airflow": _term(DATA, r"\bAirflow\b", company="astronomer"),
    "dbt": _term(
        DATA, r"(?<![\w.\-/])(?:dbt|DBT)(?![\w\-])", near=DATA_NEAR, company="dbt"
    ),
    "Databricks": _term(DATA, r"(?i:\bdatabricks\b)", company="databricks"),
    "Flink": _term(DATA, r"(?i:\bflink\b)"),
    "Hadoop": _term(DATA, r"(?i:\bhadoop\b|\bhdfs\b)"),
    "OpenAI": _term(AI, r"(?i:\bopenai\b)", company="openai"),
    "LangChain": _term(AI, r"(?i:\blang(?:chain|graph)\b)", company="langchain"),
    "Hugging Face": _term(AI, r"(?i:\bhugging\s?face\b)", company="hugging face"),
    "CUDA": _term(AI, r"(?i:\bcuda\b)"),
    # JAX-RS and JAX-WS are Java APIs.
    "JAX": _term(AI, r"\bJAX\b(?!-)", near=ML_NEAR),
    "vLLM": _term(AI, r"(?i:\bvllm\b)"),
}

TERMS = FEATURES_3_TERMS | ADDED_TERMS

GROUP_TERMS: dict[str, tuple[str, ...]] = {
    group: tuple(name for name, term in TERMS.items() if term.group == group)
    for group in GROUPS
}


def _in_list(text: str, term: Term, m: re.Match[str]) -> bool:
    before = text[max(0, m.start() - 25) : m.start()]
    after = text[m.end() : m.end() + 25]
    if NOT_A_LANGUAGE.search(before):
        return False
    return bool(LIST_BEFORE.search(before) or LIST_AFTER.search(after))


def _sentence_before(text: str, start: int) -> str:
    before = text[max(0, start - 100) : start]
    ends = list(SENTENCE_END.finditer(before))
    return before[ends[-1].end() :] if ends else before


def _counts(text: str, term: Term, m: re.Match[str], company_end: int) -> bool:
    window = text[max(0, m.start() - CONTEXT_CHARS) : m.end() + CONTEXT_CHARS]
    if term.near and not term.near.search(window):
        return False
    if term.exclude and term.exclude.search(
        text[max(0, m.start() - 30) : m.end() + 30]
    ):
        return False
    if m.start() < company_end:
        return False
    return not (
        term.company
        and (
            _company_cue(text, m)
            or COMPANY_AFTER.search(text[m.end() : m.end() + 30])
            or (
                ANALOGY_BEFORE.search(text[max(0, m.start() - 30) : m.start()])
                and ANALOGY_AFTER.search(text[m.end() : m.end() + 10])
            )
        )
    )


def _company_cue(text: str, m: re.Match[str]) -> bool:
    sentence = _sentence_before(text, m.start())
    near = " ".join(sentence.split()[-CUE_WORDS:])
    if BACKED_BY.search(near):
        return bool(INVESTOR_WORDS.search(sentence + text[m.end() : m.end() + 60]))
    if STRONG_CUE.search(near):
        return True
    return bool(COMPANY_CUE.search(near)) and not TECH_LIST.search(sentence)


def _mentions(text: str, term: Term, company_end: int) -> bool:
    if term.always and any(
        _counts(text, term, m, company_end) for m in term.always.finditer(text)
    ):
        return True
    return bool(term.in_list) and any(
        _in_list(text, term, m) and _counts(text, term, m, company_end)
        for m in term.in_list.finditer(text)
    )


# "github.com/rust-lang" or "jobs.example.com/go" is a link, not a stack mention.
URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
HEADER_FIELD = re.compile(r"\||\s[-–—]\s|\(|,|:")


# A company key matches the post's own name with or without spaces ("Hugging Face",
# "huggingface") and with a corporate suffix, but not a longer name ("Elastic Path").
OWN_SUFFIX = r"(?:\s+(?:labs?|inc|technologies|technology|ai|io|hq|cloud|computing|software|systems|nv|bv|co))?"


def _is_own(key: str, own: str) -> bool:
    squeeze = key.replace(" ", "")
    return any(
        re.fullmatch(re.escape(k) + OWN_SUFFIX, name)
        for k in (key, squeeze)
        for name in (own, own.replace(" ", ""))
    )


def stack_terms(text: str) -> list[str]:
    # A post by Datadog is not a vote for Datadog: an added term never counts in the post's
    # own company name or in the header's company field.
    text = URL.sub(" ", text)
    own = company_name(text) or ""
    lead = len(text) - len(text.lstrip())
    field = HEADER_FIELD.search(header_line(text))
    # Only a header that opens with a company name has a company field.
    company_field_end = lead + field.start() if own and field else 0
    return [
        name
        for name, term in TERMS.items()
        if not (term.company and _is_own(term.company, own))
        and _mentions(text, term, company_field_end if name in ADDED_TERMS else 0)
    ]
