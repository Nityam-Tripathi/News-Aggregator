import ReactMarkdown from "react-markdown";

const AnswerSection = ({ answer, query }: any) => {
  return (
    <div className="max-w-3xl mx-auto bg-white rounded-2xl p-6 shadow-md space-y-4">
      <h2 className="text-lg font-semibold">
        Answer for: <span className="text-primary">{query}</span>
      </h2>

      <div className="prose prose-sm max-w-none">
        <ReactMarkdown>{answer}</ReactMarkdown>
      </div>
    </div>
  );
};

export default AnswerSection;