from pathlib import Path
import re
import pymupdf
from docx import Document

SKILLS={"Python":["python"],"Java":["java"],"C#":["c#","c sharp"],"JavaScript":["javascript","js"],"TypeScript":["typescript"],"FastAPI":["fastapi"],"Flask":["flask"],"Django":["django"],"Spring Boot":["spring boot"],".NET":[".net","dotnet"],"Azure":["microsoft azure","azure"],"Azure Functions":["azure functions","azure function","function app"],"Azure OpenAI":["azure openai","azure open ai"],"Azure AI Foundry":["azure ai foundry","ai foundry"],"AWS":["aws","amazon web services"],"GCP":["gcp","google cloud platform"],"SQL":["sql"],"SQL Server":["sql server","mssql"],"PostgreSQL":["postgresql","postgres"],"MySQL":["mysql"],"MongoDB":["mongodb"],"Docker":["docker"],"Kubernetes":["kubernetes","k8s"],"Terraform":["terraform"],"Git":["git"],"GitHub":["github"],"Azure DevOps":["azure devops","ado"],"LangChain":["langchain"],"Semantic Kernel":["semantic kernel"],"OpenAI":["openai"],"RAG":["retrieval augmented generation","rag"],"Machine Learning":["machine learning"],"NLP":["natural language processing","nlp"],"REST API":["rest api","restful api","restful services"]}

def extract_text(path:Path)->str:
    if path.suffix.lower()=='.pdf':
        with pymupdf.open(path) as doc: return '\n'.join(page.get_text() for page in doc)
    if path.suffix.lower()=='.docx':
        doc=Document(path); return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
    raise ValueError('Only PDF and DOCX resumes are supported.')

def extract_skills(text:str)->list[str]:
    low=text.lower(); found=[]
    for canonical,aliases in SKILLS.items():
        if any(re.search(r'(?<![a-z0-9])'+re.escape(a.lower())+r'(?![a-z0-9])',low) for a in aliases): found.append(canonical)
    return sorted(set(found),key=str.lower)
