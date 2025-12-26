const ALLOWED_TAGS = new Set([
  'b',
  'strong',
  'i',
  'em',
  'u',
  'p',
  'br',
  'div',
  'span',
  'h1',
  'h2',
  'h3',
  'h4',
  'ul',
  'ol',
  'li',
  'blockquote'
]);

export function sanitizeRichText(html: string) {
  if (!html) {
    return '';
  }

  if (typeof DOMParser === 'undefined') {
    return html;
  }

  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');

  doc.body.querySelectorAll('*').forEach((el) => {
    const tag = el.tagName.toLowerCase();
    if (!ALLOWED_TAGS.has(tag)) {
      const parent = el.parentElement;
      if (!parent) {
        el.remove();
        return;
      }
      while (el.firstChild) {
        parent.insertBefore(el.firstChild, el);
      }
      parent.removeChild(el);
      return;
    }

    Array.from(el.attributes).forEach((attr) => el.removeAttribute(attr.name));
  });

  return doc.body.innerHTML;
}
