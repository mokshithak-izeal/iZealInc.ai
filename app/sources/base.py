from dataclasses import dataclass
@dataclass
class IncomingJob:
    source_id:str
    title:str
    job_url:str
    description:str
