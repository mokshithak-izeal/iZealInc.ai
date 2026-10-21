from app.agents.job_postprocess import complete_profile, fallback_profile, find_skills, split_sections
from app.models.job import JobProfile

APPLE_JD = """Summary
Do you want to help build some of the largest and most consequential enterprise and customer technology systems in the world? Join Apple's Information Systems and Technology (IS&T) organization.

Description
You will work within a globally distributed engineering organization supporting Finance business processes and analytical applications.
You should be comfortable working across the stack - from backend APIs and data processing to databases and modern user interfaces.

Responsibilities
Design, develop, test, and operate scalable reporting and analytical applications for Apple Finance business users.
Build backend services and APIs primarily using Python and FastAPI.
Develop responsive, intuitive web applications using React, JavaScript/TypeScript, and Node.js.
Design APIs and services that expose analytical, transactional, and financial data securely and efficiently.
Work with large datasets using SQL and modern analytical data platforms.
Develop automated unit, integration, API, and UI tests.
Contribute to CI/CD pipelines and modern deployment practices.

Minimum Qualifications
3+ years of professional software engineering or data application development experience.
Strong programming skills in Python with good understanding of object-oriented and functional programming concepts.
Experience developing production APIs or backend applications using FastAPI, Flask, Django, or comparable Python frameworks.
Strong understanding of REST APIs, HTTP fundamentals, API contracts, error handling, authentication, and service integration.
Experience developing modern web applications using React and JavaScript/TypeScript.
Experience with Node.js and modern frontend/backend development tooling.
Strong SQL skills and practical experience working with relational or analytical databases.
Experience with databases/data platforms such as Snowflake, Oracle, PostgreSQL, SingleStore, or similar technologies.
Understanding of software engineering fundamentals including data structures, algorithms, object-oriented design, API design, testing, debugging, and version control.
Experience writing automated unit and integration tests.
Experience using Git and participating in collaborative development and code-review workflows.

Preferred Qualifications
Experience building reporting, analytics, financial, accounting, payments, commerce, or enterprise applications.
Experience with Snowflake and large-scale analytical datasets.
Experience with data engineering technologies and concepts including ETL/ELT, data pipelines, data modelling, data quality, and orchestration.
Experience with Apache Spark / PySpark.
Exposure to event-driven systems such as Kafka.
Experience with NoSQL databases such as Cassandra or similar distributed data stores.
Experience with cloud platforms such as AWS, GCP, or Azure.
Experience with containers and orchestration technologies such as Docker and Kubernetes.
Experience with frontend testing frameworks such as Jest, React Testing Library, or Playwright.
Experience with Python testing frameworks such as pytest.

At Apple, we believe accessibility is a fundamental human right.
"""

# The earlier job you tested, pasted as one long line with inline headings.
INLINE_JD = ("Position: Full Stack Engineer. Roles & Responsibilities: - Expected to perform independently and become an SME. "
             "- Contribute in providing solutions to work related problems. Professional & Technical Skills: - Must To Have Skills: "
             "Proficiency in Java Full Stack Development. - Strong understanding of front-end technologies such as HTML, CSS, and "
             "JavaScript. - Experience with backend frameworks and technologies, including Spring and Hibernate. - Familiarity with "
             "database management systems, particularly SQL and NoSQL databases. - Knowledge of cloud technologies and deployment "
             "strategies. Additional Information: - The candidate should have minimum 3 years of experience in Java Full Stack "
             "Development. - This position is based at our Hyderabad office. - A 15 years full time education is required.")


def test_apple_sections_are_split():
    s = split_sections(APPLE_JD)
    assert 'FastAPI, Flask, Django' in s['required']
    assert 'Kafka' in s['preferred'] and 'Kafka' not in s['required']
    assert 'Build backend services' in s['responsibilities']


def test_apple_required_skills_found():
    fb = fallback_profile(APPLE_JD)
    for skill in ['Python', 'FastAPI', 'Flask', 'Django', 'React', 'JavaScript', 'TypeScript', 'Node.js', 'SQL',
                  'Snowflake', 'Oracle', 'PostgreSQL', 'SingleStore', 'REST API', 'Git', 'Data structures',
                  'Algorithms', 'API design', 'Unit testing']:
        assert skill in fb['required_skills'], skill


def test_apple_preferred_skills_found_and_not_duplicated():
    fb = fallback_profile(APPLE_JD)
    for skill in ['Apache Spark', 'PySpark', 'Kafka', 'Cassandra', 'AWS', 'GCP', 'Azure', 'Docker', 'Kubernetes',
                  'Jest', 'React Testing Library', 'Playwright', 'pytest', 'NoSQL', 'ETL']:
        assert skill in fb['preferred_skills'], skill
    assert 'Snowflake' not in fb['preferred_skills']   # already required


def test_apple_experience_and_responsibilities():
    fb = fallback_profile(APPLE_JD)
    assert fb['minimum_experience_years'] == 3.0
    assert len(fb['responsibilities']) >= 5


def test_empty_ai_result_is_completed():
    empty = JobProfile(title='Full Stack Engineer')
    done = complete_profile(empty, APPLE_JD)
    assert 'Python' in done.required_skills and 'FastAPI' in done.required_skills
    assert done.minimum_experience_years == 3.0
    assert done.title == 'Full Stack Engineer'
    assert any('by rules' in n for n in done.extraction_notes)


def test_good_ai_result_is_left_alone():
    good = JobProfile(required_skills=['Python'], preferred_skills=['Kafka'], minimum_experience_years=5)
    done = complete_profile(good, APPLE_JD)
    assert done.required_skills == ['Python'] and done.minimum_experience_years == 5
    assert done.extraction_notes == []


def test_inline_description_style():
    fb = fallback_profile(INLINE_JD)
    for skill in ['Java', 'HTML', 'CSS', 'JavaScript', 'Spring', 'Hibernate', 'SQL', 'NoSQL']:
        assert skill in fb['required_skills'], skill
    assert fb['minimum_experience_years'] == 3.0     # not the 15-year education line


def test_no_false_positives_from_plain_words():
    assert find_skills('The rest of the team will go to the spring offsite and express thanks.') == []
    assert find_skills('We use JavaScript and Java.') == ['JavaScript', 'Java']
