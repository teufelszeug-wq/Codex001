"""Evidence-aware per-race operational completion audit.

A forecaster label in a single generated narrative is not an independent run.
This audit does not create predictions or upgrade unverified forecasts.
"""
import json
from pathlib import Path

def audit_operations(targets, artifacts):
    result=[]
    for target in targets["targets"]:
        rid=target["race_id"]
        items=[a for a in artifacts if a.get("race_id")==rid]
        pre=[a for a in items if a.get("kind")=="forecast" and
             a.get("pre_off_verified") is True and a.get("evidence_url") and
             a.get("saved_at") and a.get("version")]
        paper=any(a.get("kind")=="paper" and a.get("vertical_qa_pass") is True
                  and a.get("evidence_url") for a in items)
        discussion=any(a.get("kind")=="roundtable" and
                       len(set(a.get("topics",[])))>=5 and a.get("evidence_url")
                       for a in items)
        settled=any(a.get("kind")=="settlement" and a.get("official_result_url")
                    and a.get("evidence_url") and a.get("stake_unit_yen")==100
                    for a in items)
        independent={a.get("forecaster_id") for a in pre if a.get("execution_mode")=="independent"
                     and a.get("run_id")}
        desk=any(a.get("forecaster_id")=="DESK" for a in pre)
        rio="RIO" in independent
        complete=bool(desk and rio and independent-{"RIO"} and paper and discussion and settled)
        result.append({"race_id":rid,"verified_pre_off_forecasts":len(pre),
                       "desk_verified":desk,"rio_independent_verified":rio,
                       "specialist_independent_count":len(independent-{"RIO"}),
                       "five_topic_roundtable_verified":discussion,
                       "vertical_paper_verified":paper,"official_settlement_verified":settled,
                       "complete":complete})
    return {"schema":"prism.operations_completion/v1","target_count":len(result),
            "complete_count":sum(x["complete"] for x in result),
            "status":"CRITICAL" if not any(x["verified_pre_off_forecasts"] for x in result) else
                     ("COMPLETE" if all(x["complete"] for x in result) else "INCOMPLETE"),
            "races":result}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--targets",required=True,type=Path)
    p.add_argument("--artifacts",required=True,type=Path)
    a=p.parse_args()
    print(json.dumps(audit_operations(json.loads(a.targets.read_text()),
                                      json.loads(a.artifacts.read_text())),ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
