"""Contrastive screening evaluation. Original and additional cases reported separately."""
import json
from pathlib import Path
from app.answer_quality import assess_answer

def evaluate(cases, corpus):
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
    return {"cases":len(rows),"true_positive":tp,"false_positive":fp,"true_negative":tn,"false_negative":fn,
        "flag_precision":round(precision,4),"flag_recall":round(recall,4),
        "flag_f1":round(2*precision*recall/(precision+recall),4) if precision+recall else 0,
        "accuracy":round((tp+tn)/len(rows),4),"results":rows}

def main():
    base=Path(__file__).parent/"fixtures"
    corpus={a["id"]:a for a in json.loads((base/"news_retrieval.json").read_text())["articles"]}
    original=evaluate(json.loads((base/"answer_quality.json").read_text())["cases"],corpus)
    additional=evaluate(json.loads((base/"answer_quality_additional.json").read_text())["cases"],corpus)
    report={"original":original,"additional":additional,
            "note":"Original cases used for tuning; additional cases are authored regression examples, not independent holdout. No live LLM generation or semantic entailment claim."}
    Path("answer-quality-report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    assert all(r["flagged"] for group in (original,additional) for r in group["results"] if r["category"]=="citation")
    assert all(r["flagged"] for r in original["results"] if r["id"] in ("reversed_roles","wrong_word_number"))
    assert original["false_positive"]==0, "Original supported examples regressed"

if __name__=="__main__":
    main()
