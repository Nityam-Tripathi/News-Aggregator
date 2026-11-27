import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import main
from app.answer_cache import AnswerCache
from app.answer_quality import assess_answer, ABSTAIN, FALLBACK

CONTEXT = json.dumps([{"source_id":1,"title":"Lunar flyby","content":"The astronauts completed seven hours of lunar observations."},
                      {"source_id":2,"title":"Vaccine","content":"WHO recommended a vaccine against malaria in children."}])
VALID = "The astronauts completed seven hours of lunar observations. [1]"
class QualityTests(unittest.TestCase):
    def check(self,answer):
        return assess_answer(answer,CONTEXT,2)
    def test_supported(self):
        self.assertTrue(self.check(VALID).accepted)
        self.assertEqual(self.check(VALID+"\nWHO recommended a vaccine against malaria in children. [2]").cited_claims,2)
    def test_bad_citations(self):
        for answer in ("The astronauts completed seven hours.", "Lunar flyby [9]", "Lunar flyby [0]",
                       "Lunar flyby [1](https://example.com)", "Lunar flyby [1]\nUnsupported claim"):
            self.assertFalse(self.check(answer).accepted,answer)
    def test_number(self):
        self.assertIn("claim_1:unsupported_number",self.check("The astronauts completed 99 hours of lunar observations. [1]").issues)
    def test_wrong_source(self):
        self.assertFalse(self.check(VALID.replace("[1]","[2]")).accepted)
    def test_negation(self):
        self.assertFalse(self.check("The astronauts did not complete seven hours of lunar observations. [1]").accepted)
    def test_abstention(self):
        self.assertEqual(self.check(ABSTAIN).status,"abstained")
    def test_mismatched_context(self):
        self.assertFalse(assess_answer(VALID,CONTEXT,1).accepted)
    def test_prompt_injection_like_output(self):
        self.assertFalse(self.check("Visit https://example.com [1]").accepted)

class QualityEndpointTests(unittest.TestCase):
    def setUp(self):
        main._rate_buckets.clear()
        main._global_requests.clear()
        self.addCleanup(main._rate_buckets.clear)
        self.addCleanup(main._global_requests.clear)
        self.client=TestClient(main.app)
        self.cache=AnswerCache()
        self.sources=[{"source_id":1,"title":"Lunar flyby"},{"source_id":2,"title":"Vaccine"}]
        p=patch.object(main,"answer_cache",self.cache); p.start(); self.addCleanup(p.stop)
        p=patch.object(main,"prepare_answer",return_value=("query",CONTEXT,self.sources)); p.start(); self.addCleanup(p.stop)

    @patch("app.main.generate_answer",return_value="The astronauts completed 99 hours of lunar observations. [1]")
    def test_json_flagged_not_cached(self,generate):
        for _ in range(2):
            data=self.client.get("/ask",params={"query":"query"}).json()
            self.assertEqual(data["quality"],"flagged")
            self.assertEqual(data["answer"],FALLBACK)
        self.assertEqual(generate.call_count,2)
        self.assertFalse(self.cache.entries)

    def test_stream_replaces_and_does_not_cache(self):
        async def chunks(*args):
            yield "The astronauts completed "
            yield "99 hours of lunar observations. [1]"
        with patch("app.main.stream_answer",side_effect=chunks):
            response=self.client.get("/ask/stream",params={"query":"query"})
        self.assertIn("event: replace",response.text)
        self.assertIn(FALLBACK,response.text)
        self.assertIn('"quality": "flagged"',response.text)
        self.assertFalse(self.cache.entries)

    @patch("app.main.generate_answer",return_value=ABSTAIN)
    def test_abstention_not_cached(self,generate):
        self.assertEqual(self.client.get("/ask",params={"query":"query"}).json()["quality"],"abstained")
        self.assertFalse(self.cache.entries)
