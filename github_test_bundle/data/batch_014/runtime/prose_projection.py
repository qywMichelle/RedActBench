"""Conservative prose spacing for new control variants, preserving machine payloads."""
from copy import deepcopy
import re
from language_patches import spacing,NARRATIVE_KEYS

def normalize(case):
 out=deepcopy(case);translations=out.setdefault('translations',{})
 def walk(v):
  if isinstance(v,dict):
   for key,value in list(v.items()):
    if key=='translations':continue
    if isinstance(value,str) and key in NARRATIVE_KEYS:
     revised=spacing(value)
     revised=re.sub(r'\b(Your|Our|Their|Total|net|Net|shared|service|mature|fresh|stock|balance|input|accepted|linked|combined|total)(?=\d)',r'\1 ',revised)
     revised=re.sub(r'(?<=\d)(kg|yuan|grams)\b',r' \1',revised)
     revised=re.sub(r'\b([Aa])(?=\d+-yuan)',r'\1 ',revised)
     if revised!=value and value in translations:translations[revised]=translations[value]
     v[key]=revised
    else:walk(value)
  elif isinstance(v,list):
   for child in v:walk(child)
 walk(out);return out
