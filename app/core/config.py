#app/config.py
# Curated keyword normalization config for job matching.
# Goal:
# - preserve valuable short technical terms
# - normalize common variants to canonical forms
# - remove common low-signal words
# - improve tag overlap quality without replacing embeddings
# Layer	Responsibility
# embeddings	semantic retrieval
# aliases	normalization
# expansions	ATS vocabulary widening
# tags	clean symbolic concepts
# keywords	recruiter phrasing metadata

STOPWORDS = {
    # common filler / grammar
    "the", "and", "for", "with", "you", "your", "yours",
    "our", "ours", "they", "their", "them",
    "this", "that", "these", "those",
    "are", "was", "were", "been", "being", "is",
    "have", "has", "had",
    "will", "would", "should", "could", "can",
    "from", "into", "onto", "upon", "over", "under",
    "about", "around", "through", "within", "across",
    "who", "what", "when", "where", "why", "how",
    "seeking", "looking", "join", "role", "position",
    "candidate", "ideal", "preferred", "required",
    "responsibilities", "responsibility", "include", "includes",
    "including", "assist", "supporting", "working",
    "strong", "excellent", "good", "great",
    "ability", "skills", "skill", "knowledge",
    "experience", "experienced",
    "team", "teams", "environment", "company",
    "internal", "external", "various", "multiple",
    "etc",
    # generic verbs / filler that add noise to keyword overlap
    "way", "real", "solo", "fast", "like", "high", "stay",
    "step", "top", "fix", "find", "keep", "make", "shape",
    "think", "every", "used", "level", "field", "before",
    "become", "best", "current", "previous", "initial",
    "regular", "common", "manual", "personal", "clear",
    "clearly", "build", "write", "dig", "work", "job",
    "non", "use", "set", "see", "run", "get", "put",
    "all", "also", "just", "may", "per", "not", "more",
    "most", "each", "well", "once", "need", "new",
    "key", "based", "help", "take", "give", "show",
    "end", "turn", "move", "pay", "say", "let", "got"
}

# Canonical terms we care about preserving / boosting
KNOWN_TERMS = {
    # programming / scripting
    "python", "java", "javascript", "typescript", "bash",
    "powershell", "sql", "html", "css",

    # frameworks / backend
    "fastapi", "flask", "django", "node", "react",

    # infra / cloud
    "aws", "azure", "gcp", "docker", "kubernetes",
    "linux", "windows", "vmware",

    # networking / security
    "tcp", "udp", "dns", "dhcp", "vpn",
    "firewall", "siem", "splunk", "soc",
    "ids", "ips", "edr", "xdr",
    "phishing", "malware", "threat", "incident",
    "vulnerability", "iam", "mfa",

    # support / IT
    "it", "helpdesk", "ticketing", "jira",
    "servicenow", "active", "directory",

    # data / analytics
    "excel", "powerbi", "tableau",

    # short modern terms
    "ai", "ml", "ui", "ux", "qa", "ci", "cd",

    # resume / generic useful terms
    "api", "apis"
}

# Variant -> canonical token
ALIASES = {
    # api
    "apis": "api",
    "api's": "api",
    "rest": "api",
    "restful": "api",
    "graphql": "api",

    # javascript ecosystem
    "js": "javascript",
    "nodejs": "node",
    "node.js": "node",

    # cloud
    "amazon": "aws",
    "amazonwebservices": "aws",
    "azurecloud": "azure",
    "googlecloud": "gcp",

    # containers
    "containers": "docker",
    "containerization": "docker",
    "k8s": "kubernetes",
    "kube": "kubernetes",

    # operating systems
    "win": "windows",
    "windowsserver": "windows",
    "ubuntu": "linux",
    "debian": "linux",

    # security
    "securityoperationscenter": "soc",
    "secops": "soc",
    "socanalyst": "soc",
    "monitoring": "siem",
    "splunkenterprise": "splunk",

    # identity
    "activedirectory": "directory",
    "ad": "directory",
    "multifactorauthentication": "mfa",

    # incidents
    "incidents": "incident",
    "alerts": "alert",
    "detections": "detection",

    # support
    "helpdesktechnician": "helpdesk",
    "helpdeskanalyst": "helpdesk",
    "tickets": "ticketing",

    # people / grammar normalization
    "analysts": "analyst",
    "engineers": "engineer",
    "developers": "developer",
    "systems": "system",
    "servers": "server",
    "users": "user",

    # common soft skills normalization
    "communicating": "communication",
    "communicator": "communication",
    "collaborative": "collaboration",
    "organized": "organization"
}


WEIGHTS = {
    "similarity": 0.72,
    "tag": 0.13,
    "priority": 0.15
}


QUOTAS = {
    "experience": 5,
    "project": 5,
    "skill": 20,
    "summary": 1,
    "education": 2
}

# Max bullets selected from any single group_key within experience or project pools.
# Prevents one project/role from consuming the entire type quota.
GROUP_CAP = 3

TEMPLATE_NAME = "technical_compact"

MIN_SCORE = 0.50
SKILL_MIN_SCORE = 0.43  # skills are short chunks — lower threshold prevents systematic under-selection
EDUCATION_MIN_SCORE = 0.44  # edu chunks score ~0.47–0.49 on target tech JDs; retail/unrelated JDs score much lower and are cut naturally


# =========================================================
# Rewrite controls
# =========================================================

ENABLE_REWRITES = False

REWRITE_SECTIONS = {
    "summary": True,
    "experience": True,
    "projects": True
}


TIMEZONE = "America/Montreal"
# Others
# "UTC"

# "America/Montreal"
# "America/Toronto"
# "America/New_York"
# "America/Chicago"
# "America/Denver"
# "America/Los_Angeles"

# "Europe/London"
# "Europe/Paris"

# "Asia/Tokyo"
# "Asia/Dubai"

# "Australia/Sydney"