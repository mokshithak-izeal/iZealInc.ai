from fastapi import APIRouter
from pydantic import BaseModel,Field
from app.database.preferences import load_preferences,save_preferences
router=APIRouter(prefix='/api/preferences',tags=['preferences'])
class P(BaseModel):preferred_role:str='';preferred_locations:list[str]=[];work_modes:list[str]=[];minimum_match:int=Field(80,ge=0,le=100);excluded_companies:list[str]=[]
@router.get('')
def get():return load_preferences()
@router.put('')
def put(req:P):return save_preferences(req.model_dump())
