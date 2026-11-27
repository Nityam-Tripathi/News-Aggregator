export type StreamCallbacks = {
  onSources: (sources: any[]) => void;
  onDelta: (text: string) => void;
};

export async function consumeAnswerStream(response: Response, callbacks: StreamCallbacks) {
  if (!response.body || !response.headers.get("content-type")?.includes("text/event-stream")) {
    throw new Error("Unexpected streaming response.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", complete = false;
  let hasText = false;
  try {
    while (!complete) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const lines = block.split("\n");
        const event = lines.find(line => line.startsWith("event:"))?.slice(6).trim();
        const raw = lines.filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
        if (!raw) continue;
        const data = JSON.parse(raw);
        if (event === "sources") {
          if (!Array.isArray(data)) throw new Error("Invalid sources.");
          callbacks.onSources(data);
        } else if (event === "delta") {
          if (typeof data.text !== "string") throw new Error("Invalid answer chunk.");
          hasText ||= !!data.text.trim();
          callbacks.onDelta(data.text);
        } else if (event === "error") {
          throw new Error(typeof data.message === "string" ? data.message : "Answer interrupted.");
        } else if (event === "done") {
          complete = true;
          break;
        }
      }
      if (done) break;
    }
    if (!complete || !hasText) throw new Error("Answer stream interrupted. Please retry.");
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
