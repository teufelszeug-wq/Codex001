import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from prism_paper.release_gate import validate_morning_edition

class ReleaseGateTests(unittest.TestCase):
    def test_rejects_preview_and_missing_evidence(self):
        result=validate_morning_edition({"edition_type":"RESEARCH_PREVIEW"})
        self.assertFalse(result["approved"])
        self.assertIn("approved production renderer not used",result["errors"])
        self.assertIn("actual PDF artifact missing",result["errors"])
    def test_rejects_unreviewed_paper(self):
        record={"edition_type":"MORNING_FINAL","renderer_id":"prism.mpaper.production",
                "layout_qa":{"vertical_all_pages":True,"visual_proof_reviewed":False,
                             "horse_columns_complete":True,"newspaper_hierarchy_passed":True},
                "forecast":{"pre_off_saved":True,"all_runners_covered":True,"independent_agents_verified":True},
                "editorial":{"five_topics_complete":True,"character_db_verified":True},
                "artifact":{"pdf_path":"edition.pdf"}}
        self.assertFalse(validate_morning_edition(record)["approved"])
        record["layout_qa"]["visual_proof_reviewed"]=True
        self.assertTrue(validate_morning_edition(record)["approved"])
if __name__=="__main__":unittest.main()
