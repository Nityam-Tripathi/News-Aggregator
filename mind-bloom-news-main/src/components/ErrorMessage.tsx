import { SearchX } from "lucide-react";
import { motion } from "framer-motion";

interface ErrorMessageProps {
  message?: string;
}

const ErrorMessage = ({ message = "No results found. Try a different query." }: ErrorMessageProps) => (
  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center py-12 text-center">
    <div className="p-4 rounded-2xl bg-muted mb-4">
      <SearchX size={28} className="text-muted-foreground" />
    </div>
    <p className="text-muted-foreground text-sm">{message}</p>
  </motion.div>
);

export default ErrorMessage;
