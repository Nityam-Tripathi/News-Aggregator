import { test } from "node:test";
import assert from "node:assert/strict";
import { splitCitations } from "../src/lib/citations.ts";
test("only valid source IDs become citation links",()=>{
  const parts=splitCitations("Claim [1] [2] [0] [99] [99999999999999999999999]",2);
  assert.deepEqual(parts.filter(p=>p.sourceId!==null).map(p=>p.sourceId),[1,2]);
  assert.equal(parts.map(p=>p.text).join(""),"Claim [1] [2] [0] [99] [99999999999999999999999]");
});
test("draft citations remain plain text",()=>{
  assert.equal(splitCitations("Claim [1]",0)[1].sourceId,null);
});
