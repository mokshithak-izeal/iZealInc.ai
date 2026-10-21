"""Rule-based safety net for job-description parsing.

It reads the job text itself (section headings, bullet lines, a list of known
technologies) so a result is still produced when the AI returns empty lists.
No network or AI calls happen here.
"""
import re

HEAD_REQ = (r"(?:minimum|basic|required|key|mandatory|essential|core)\s+(?:qualifications?|requirements?|skills?)"
            r"|requirements?|qualifications?|must[- ]have(?:\s+skills)?|what you(?:’|')?ll bring"
            r"|what we(?:’|')?re looking for|professional\s*(?:&|and)\s*technical skills|technical skills"
            r"|skills required|must to have skills")
HEAD_PREF = (r"(?:preferred|desired|desirable|additional|bonus)\s+(?:qualifications?|requirements?|skills?|experience)"
             r"|nice[- ]to[- ]have(?:\s+skills)?|good[- ]to[- ]have(?:\s+skills)?|bonus points")
HEAD_RESP = (r"(?:key\s+)?responsibilit(?:y|ies)|roles?\s*(?:&|and)\s*responsibilit(?:y|ies)"
             r"|what you(?:’|')?ll do|duties|the role")
HEAD_OTHER = r"summary|description|job description|about (?:us|the role|the team|apple|you)|benefits|overview"
ANY_HEAD = f"{HEAD_PREF}|{HEAD_RESP}|{HEAD_REQ}|{HEAD_OTHER}"


def _t(name, *aliases, cs=False):
    return (name, (name,) + aliases, cs)


# (canonical name, spellings to look for, case-sensitive?)
LEXICON = [
    _t('Python'), _t('Java'), _t('JavaScript'), _t('TypeScript'), _t('C++'), _t('C#'), _t('Rust'),
    _t('Kotlin'), _t('Swift', cs=True), _t('Scala'), _t('Ruby', cs=True), _t('PHP'), _t('SQL'),
    _t('PL/SQL'), _t('Bash'), _t('PowerShell'), _t('Golang'),
    _t('React', 'React.js', 'ReactJS', cs=True), _t('Angular', cs=True), _t('Vue', 'Vue.js', 'VueJS', cs=True),
    _t('Next.js'), _t('Node.js', 'NodeJS'), _t('HTML', 'HTML5'), _t('CSS', 'CSS3'), _t('Redux'),
    _t('jQuery'), _t('Tailwind CSS'), _t('Jest', cs=True), _t('React Testing Library'), _t('Playwright'),
    _t('Cypress', cs=True), _t('Selenium'), _t('Webpack'),
    _t('FastAPI'), _t('Flask', cs=True), _t('Django'), _t('Spring Boot'), _t('Spring', cs=True),
    _t('Hibernate'), _t('Express.js'), _t('.NET'), _t('ASP.NET'), _t('GraphQL'), _t('gRPC'),
    _t('Microservices', 'microservice'),
    _t('REST API', 'REST APIs', 'RESTful APIs', 'RESTful services', 'RESTful API', 'RESTful'),
    _t('REST API', 'REST', cs=True),
    _t('Snowflake'), _t('Oracle', cs=True), _t('PostgreSQL', 'Postgres'), _t('MySQL'), _t('SQL Server'),
    _t('MongoDB'), _t('DynamoDB'), _t('Cassandra'), _t('Redis'), _t('SingleStore'), _t('Elasticsearch'),
    _t('NoSQL'), _t('Apache Spark', 'Spark', cs=True), _t('PySpark'), _t('Kafka', 'Apache Kafka'),
    _t('Airflow', 'Apache Airflow'), _t('dbt', cs=True), _t('Hadoop'), _t('Databricks'),
    _t('ETL', cs=True), _t('ELT', cs=True), _t('Data modelling', 'data modeling'),
    _t('Data pipelines', 'data pipeline'),
    _t('AWS', 'Amazon Web Services'), _t('Azure', cs=True), _t('GCP', 'Google Cloud'), _t('Docker'),
    _t('Kubernetes', 'K8s'), _t('Terraform'), _t('Jenkins'), _t('GitHub Actions'), _t('CI/CD'),
    _t('Git', cs=True), _t('Linux'), _t('Ansible'),
    _t('Prometheus'), _t('Grafana'), _t('OpenTelemetry'), _t('Splunk'), _t('Datadog'),
    _t('pytest', cs=True), _t('JUnit'),
    _t('Unit testing', 'unit tests', 'unit test', 'automated unit', 'unit and integration'),
    _t('Integration testing', 'integration tests', 'integration test'),
    _t('TensorFlow'), _t('PyTorch'), _t('scikit-learn', 'scikit learn'), _t('Pandas', cs=True),
    _t('NumPy'), _t('LangChain'), _t('Machine learning'), _t('Generative AI'), _t('LLM', cs=True),
    _t('OAuth', 'OAuth 2.0', 'OAuth2'), _t('JWT', cs=True), _t('SAML', cs=True),
    _t('Data structures'), _t('Algorithms', 'algorithms'),
    _t('Object-oriented programming', 'object-oriented', 'object oriented', 'OOP'),
    _t('Functional programming'), _t('API design'),
]


def _compile(alias, cs):
    return re.compile(r'(?<![A-Za-z0-9])' + re.escape(alias) + r'(?![A-Za-z0-9+#])', 0 if cs else re.I)


_PATTERNS = [(name, _compile(a, cs)) for name, aliases, cs in LEXICON for a in aliases]


def find_skills(text):
    """Known technologies in `text`, in order of first appearance, no duplicates."""
    hits = {}
    for name, pattern in _PATTERNS:
        m = pattern.search(text or '')
        if m and (name not in hits or m.start() < hits[name]):
            hits[name] = m.start()
    return [n for n, _ in sorted(hits.items(), key=lambda kv: kv[1])]


def _heading(text):
    t = re.sub(r'^[\s\-•*#\d.)]+', '', text).strip().rstrip(':').strip().lower()
    for kind, pat in (('preferred', HEAD_PREF), ('responsibilities', HEAD_RESP),
                      ('required', HEAD_REQ), ('other', HEAD_OTHER)):
        if re.fullmatch(pat, t):
            return kind
    return None


def split_sections(text):
    """Return {'required': str, 'preferred': str, 'responsibilities': str, 'other': str}."""
    text = (text or '').replace('\r', '')
    # Descriptions pasted as one long line: start a new line before an inline "Heading:".
    text = re.sub(rf'(?i)(?<=[.\s])({ANY_HEAD})\s*:', r'\n\1:', text)
    out = {'required': [], 'preferred': [], 'responsibilities': [], 'other': []}
    current = 'other'
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        head, sep, rest = line.partition(':')
        kind = _heading(head) if sep and len(head) < 60 else None
        if kind is None and len(line) < 60:
            kind = _heading(line)
            rest = ''
        if kind:
            current = kind
            if rest.strip():
                out[current].append(rest.strip())
            continue
        out[current].append(line)
    return {k: '\n'.join(v) for k, v in out.items()}


def _years(text):
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)', text, re.I):
        return float(m.group(1)), float(m.group(2))
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)', text, re.I):
        around = text[max(0, m.start() - 40): m.end() + 40].lower()
        if 'education' in around or 'degree' in around:
            continue
        return float(m.group(1)), None
    return None, None


def _bullets(text, limit=15):
    items = []
    for line in text.split('\n'):
        line = re.sub(r'^[\s\-•*\d.)]+', '', line).strip()
        if 15 <= len(line) <= 300:
            items.append(line.rstrip('.'))
    return items[:limit]


def fallback_profile(text):
    sections = split_sections(text)
    has_sections = bool(sections['required'] or sections['preferred'])
    required_text = sections['required'] or ('' if has_sections else sections['other'])
    required = find_skills(required_text)
    seen = {s.lower() for s in required}
    preferred = [s for s in find_skills(sections['preferred']) if s.lower() not in seen]
    low, high = _years(required_text) if required_text else (None, None)
    if low is None:
        low, high = _years(text)
    return {'required_skills': required, 'preferred_skills': preferred,
            'responsibilities': _bullets(sections['responsibilities']),
            'minimum_experience_years': low, 'maximum_experience_years': high}


def complete_profile(profile, text):
    """Fill gaps in an AI-produced JobProfile using the job text. Returns the same object."""
    fb = fallback_profile(text)
    notes = list(profile.extraction_notes or [])
    if not profile.required_skills and fb['required_skills']:
        profile.required_skills = fb['required_skills']
        taken = {s.lower() for s in profile.required_skills}
        if not profile.preferred_skills:
            profile.preferred_skills = [s for s in fb['preferred_skills'] if s.lower() not in taken]
        notes.append('The AI returned no required skills, so skills were read from the job text by rules.')
    if not profile.responsibilities and fb['responsibilities']:
        profile.responsibilities = fb['responsibilities']
    if profile.minimum_experience_years is None and fb['minimum_experience_years'] is not None:
        profile.minimum_experience_years = fb['minimum_experience_years']
        if profile.maximum_experience_years is None:
            profile.maximum_experience_years = fb['maximum_experience_years']
    profile.extraction_notes = notes
    return profile
