import { test } from "node:test";
import assert from "node:assert/strict";
import { consumeAnswerStream } from "../src/lib/answerStream.ts";

function response(text, sizes=[1,7,13]) {
  const bytes = new TextEncoder().encode(text);
  let offset=0, index=0;
  return new Response(new ReadableStream({
    pull(controller) {
      if (offset>=bytes.length) { controller.close(); return; }
      const size=sizes[index++ % sizes.length];
      controller.enqueue(bytes.slice(offset,offset+size));
      offset+=size;
    }
  }), {headers:{"content-type":"text/event-stream"}});
}
const event = (name,data)=>"event: "+name+"\ndata: "+JSON.stringify(data)+"\n\n";

test("decodes split SSE frames and UTF-8",async()=>{
  let text="", sources;
  await consumeAnswerStream(response(event("sources",[{title:"News"}])+event("delta",{text:"नमस्ते "})+event("delta",{text:"world"})+event("done",{})),{
    onSources:x=>sources=x, onDelta:x=>text+=x
  });
  assert.deepEqual(sources,[{title:"News"}]);
  assert.equal(text,"नमस्ते world");
});
test("rejects truncated stream",async()=>{
  await assert.rejects(consumeAnswerStream(response(event("delta",{text:"partial"})),{
    onSources:()=>{},onDelta:()=>{}
  }),/interrupted/);
});
test("rejects explicit error",async()=>{
  await assert.rejects(consumeAnswerStream(response(event("error",{message:"provider offline"})),{
    onSources:()=>{},onDelta:()=>{}
  }),/provider offline/);
});

test("replaces provisional text after evidence screening",async()=>{
  let text="";
  await consumeAnswerStream(response(event("delta",{text:"unsupported claim"})+event("replace",{text:"Cannot verify."})+event("done",{quality:"flagged"})),{
    onSources:()=>{},onDelta:x=>text+=x,onReplace:x=>text=x
  });
  assert.equal(text,"Cannot verify.");
});
