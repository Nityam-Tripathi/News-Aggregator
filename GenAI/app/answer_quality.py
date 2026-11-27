"""Deterministic citation/evidence screening, not a semantic entailment oracle."""
import json
import re
from dataclasses import dataclass

ABSTAIN = "The retrieved news excerpts do not provide enough evidence to answer this question."
FALLBACK = "I could not verify the answer against the retrieved news excerpts. Please try a more specific question."
CITATION = re.compile(r"\[([1-9][0-9]*)\]")
TAIL = re.compile(r"(?:\s*\[[1-9][0-9]*\])+\s*[.!?]?\s*$")
NUMBER = re.compile(r"(?<!\w)[+-]?\d[\d,]*(?:\.\d+)?%?")
STOP = set("a an the and or of to in on at for by with from as is are was were be been being that this it its they their has have had will would could should can may reported reports according said says".split())
NEGATION = re.compile(r"\b(?:not|never|no|none|without|cannot|didn't|doesn't|wasn't|weren't|isn't|aren't|can't)\b", re.I)
MIN_OVERLAP = .60

@dataclass(frozen=True)
class QualityResult:
    accepted: bool
    status: str
    claims: int
    cited_claims: int
    issues: tuple

def evidence_context(articles):
    return json.dumps([{"source_id":i,"title":a.title or "",
                        "content":a.content or "",
                        "published_at":a.published_at.isoformat() if a.published_at else None}
                       for i,a in enumerate(articles,1)], ensure_ascii=False)

def words(value):
    return {w for w in re.findall(r"[\w]+",value.casefold()) if w not in STOP}

def numbers(value):
    return {x.replace(",","") for x in NUMBER.findall(value)}

def assess_answer(answer, context, source_count):
    if answer.strip() == ABSTAIN:
        return QualityResult(True,"abstained",0,0,())
    try:
        evidence = json.loads(context)
        if not isinstance(evidence,list) or len(evidence)!=source_count:
            raise ValueError("source mismatch")
        if [row["source_id"] for row in evidence] != list(range(1,source_count+1)):
            raise ValueError("source order mismatch")
    except (ValueError,TypeError,KeyError):
        return QualityResult(False,"flagged",0,0,("invalid_evidence",))
    lines = [line.strip().removeprefix("- ").strip() for line in answer.splitlines() if line.strip()]
    issues, cited = [], 0
    if not lines:
        issues.append("empty_answer")
    for index,line in enumerate(lines,1):
        def flag(reason):
            issues.append(f"claim_{index}:{reason}")
        ids = CITATION.findall(line)
        tail = TAIL.search(line)
        if not ids or not tail:
            flag("missing_citation")
            continue
        if any(len(x)>3 or int(x)>source_count for x in ids):
            flag("invalid_citation")
            continue
        # Citations must form a suffix. Reject URLs, markdown links and other brackets.
        claim = line[:tail.start()].strip()
        if not claim or "[" in claim or "]" in claim or re.search(r"https?://|<[^>]*>",claim,re.I):
            flag("invalid_claim_format")
            continue
        cited += 1
        refs = [evidence[int(x)-1] for x in set(ids)]
        excerpts = " ".join(f"{r.get('title','')} {r.get('content','')}" for r in refs)
        if numbers(claim)-numbers(excerpts):
            flag("unsupported_number")
        claim_words = words(claim)
        if not claim_words or len(claim_words & words(excerpts))/len(claim_words)<MIN_OVERLAP:
            flag("weak_evidence_overlap")
        if NEGATION.search(claim) and not NEGATION.search(excerpts):
            flag("possible_negation")
    return QualityResult(not issues,"screened" if not issues else "flagged",len(lines),cited,tuple(issues))
