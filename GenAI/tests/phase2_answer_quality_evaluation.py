"""Deterministic screening evaluation; no Groq calls or external judge."""
import json
from pathlib import Path
from statistics import mean
from app.answer_quality import assess_answer

def main():
    base=Path(__file__).parent/"fixtures"
    corpus={a["id"]:a for a in json.loads((base/"news_retrieval.json").read_text())["articles"]}
    cases=json.loads((base/"answer_quality.json").read_text())["cases"]
    rows=[]
    for case in cases:
        evidence=[{"source_id":i,"title":corpus[key]["title"],"content":corpus[key]["content"]}
                  for i,key in enumerate(case["source_ids"],1)]
        result=assess_answer(case["answer"],json.dumps(evidence),len(evidence))
        rows.append({**case,"flagged":not result.accepted,"status":result.status,
                     "claims":result.claims,"cited_claims":result.cited_claims,"issues":result.issues})
    tp=sum(r["flagged"] and r["should_flag"] for r in rows)
    fp=sum(r["flagged"] and not r["should_flag"] for r in rows)
    tn=sum(not r["flagged"] and not r["should_flag"] for r in rows)
    fn=sum(not r["flagged"] and r["should_flag"] for r in rows)
    precision=tp/(tp+fp) if tp+fp else 0
    recall=tp/(tp+fn) if tp+fn else 0
    report={"cases":len(rows),"true_positive":tp,"false_positive":fp,"true_negative":tn,"false_negative":fn,
        "flag_precision":round(precision,4),"flag_recall":round(recall,4),
        "flag_f1":round(2*precision*recall/(precision+recall),4) if precision+recall else 0,
        "accuracy":round((tp+tn)/len(rows),4),
        "note":"Manual contrastive smoke test of a heuristic, not generated answer faithfulness or a general hallucination detector. False negatives are expected and reported.",
        "results":rows}
    Path("answer-quality-report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    # Basic integrity checks are release gates; do not claim semantic entailment.
    assert all(r["flagged"] for r in rows if r["category"]=="citation")

if __name__=="__main__":
    main()
