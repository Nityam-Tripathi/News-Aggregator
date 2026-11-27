export function splitCitations(answer: string, sourceCount: number) {
  return answer.split(/(\[[1-9][0-9]*\])/g).filter(Boolean).map(text => {
    const match = /^\[([1-9][0-9]*)\]$/.exec(text);
    const id = match ? Number(match[1]) : 0;
    return {text, sourceId: Number.isSafeInteger(id) && id > 0 && id <= sourceCount ? id : null};
  });
}
