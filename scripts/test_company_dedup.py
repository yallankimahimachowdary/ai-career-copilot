import re
import difflib

def clean_company(c: str) -> str:
    s = re.sub(r"['\"]", "", (c or "").lower())
    s = re.sub(r"^(?:lmmfs|lmmf|the|dr|m/s|ms)\b[\s,.]*", "", s)
    s = re.sub(r"\b(?:hospital|hospitals|clinic|center|centre|institute|pvt|ltd|private|limited|inc|llc|corp)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)

c1 = "MAI MAGESHKAR HOSPITAL,WARJE"
c2 = "LMMF'S Mai Mangeshkar Hospital, Warje"
cl1 = clean_company(c1)
cl2 = clean_company(c2)
print("cl1:", cl1)
print("cl2:", cl2)
print("ratio:", difflib.SequenceMatcher(None, cl1, cl2).ratio())
