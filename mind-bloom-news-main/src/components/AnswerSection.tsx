import { splitCitations } from "@/lib/citations";

interface AnswerProps {
  answer: string;
  query: string;
  sourceCount?: number;
  provisional?: boolean;
}

const AnswerSection = ({ answer, query, sourceCount = 0, provisional = false }: AnswerProps) => (
  <div className="max-w-3xl mx-auto bg-white rounded-2xl p-6 shadow-md space-y-4">
    <h2 className="text-lg font-semibold">
      Answer for: <span className="text-primary">{query}</span>
    </h2>
    {provisional && <p role="status" className="text-sm text-muted-foreground">Draft — evidence checks pending.</p>}
    <div className="prose prose-sm max-w-none whitespace-pre-wrap break-words">
      {splitCitations(answer, provisional ? 0 : sourceCount).map((part,i) =>
        part.sourceId === null ? <span key={i}>{part.text}</span> :
          <a key={i} className="inline-block rounded px-1 text-primary font-semibold" href={"#source-"+part.sourceId}
            aria-label={"Go to source "+part.sourceId}>{part.text}</a>
      )}
    </div>
  </div>
);
export default AnswerSection;
