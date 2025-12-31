const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const shouldSkipTextNode = (node: Text) => {
  const parent = node.parentElement;
  if (!parent) return true;
  const tag = parent.tagName.toLowerCase();
  return tag === 'script' || tag === 'style' || tag === 'noscript' || tag === 'textarea';
};

export function highlightPhrasesInHtml(html: string, phrases?: string[] | null) {
  if (!html) return html;
  const cleanedPhrases = Array.from(
    new Set((phrases ?? []).map((phrase) => (phrase ?? '').trim()).filter(Boolean))
  ).sort((a, b) => b.length - a.length);
  if (cleanedPhrases.length === 0) return html;

  const regex = new RegExp(cleanedPhrases.map(escapeRegExp).join('|'), 'gi');

  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');
  const textNodes: Text[] = [];
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode as Text;
    if (!node.nodeValue || shouldSkipTextNode(node)) continue;
    textNodes.push(node);
  }

  for (const node of textNodes) {
    const text = node.nodeValue ?? '';
    regex.lastIndex = 0;
    let match: RegExpExecArray | null = null;
    let lastIndex = 0;
    const fragment = doc.createDocumentFragment();

    while ((match = regex.exec(text))) {
      const start = match.index;
      const value = match[0] ?? '';
      if (start > lastIndex) {
        fragment.appendChild(doc.createTextNode(text.slice(lastIndex, start)));
      }

      const mark = doc.createElement('mark');
      mark.className = 'rounded bg-yellow-200/50 px-0.5 py-0.5';
      mark.textContent = value;
      fragment.appendChild(mark);

      lastIndex = start + value.length;
    }

    if (lastIndex === 0) continue;
    if (lastIndex < text.length) {
      fragment.appendChild(doc.createTextNode(text.slice(lastIndex)));
    }
    node.parentNode?.replaceChild(fragment, node);
  }

  return doc.body.innerHTML;
}

