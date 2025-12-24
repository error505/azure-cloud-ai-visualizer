import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import clsx from 'clsx';

interface TypewriterMarkdownProps {
  text?: string;
  speed?: number;
  className?: string;
  startImmediately?: boolean;
}

const TypewriterMarkdown: React.FC<TypewriterMarkdownProps> = ({
  text = '',
  speed = 12,
  className,
  startImmediately = true,
}) => {
  const [display, setDisplay] = useState(startImmediately ? '' : text);
  const intervalRef = useRef<number | null>(null);
  const previousTextRef = useRef<string | null>(null);

  useEffect(() => {
    const safeText = text ?? '';
    const shouldAnimate = startImmediately && safeText !== previousTextRef.current;

    if (!shouldAnimate) {
      setDisplay(safeText);
      previousTextRef.current = safeText;
      return;
    }

    if (!safeText) {
      setDisplay('');
      previousTextRef.current = safeText;
      return;
    }

    if (typeof window === 'undefined') {
      setDisplay(safeText);
      return;
    }

    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
    }

    previousTextRef.current = safeText;
    setDisplay('');
    let index = 0;
    const chunk = Math.max(1, Math.round(safeText.length / 300));
    const delay = Math.max(4, speed);

    const id = window.setInterval(() => {
      index = Math.min(safeText.length, index + chunk);
      setDisplay(safeText.slice(0, index));
      if (index >= safeText.length) {
        window.clearInterval(id);
        intervalRef.current = null;
      }
    }, delay);

    intervalRef.current = id;

    return () => {
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [text, speed, startImmediately]);

  return (
    <div className={clsx('prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap break-words', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{preserveSingleLineBreaks(display || '')}</ReactMarkdown>
    </div>
  );
};

function preserveSingleLineBreaks(input: string) {
  if (!input) return input;
  // Normalize CRLF to LF for consistent processing
  const normalized = input.replace(/\r\n/g, '\n');

  // Split into code-fence segments so we don't modify code blocks
  const fenceRegex = /```[\s\S]*?```/g;
  let lastIndex = 0;
  const parts: string[] = [];
  let match: RegExpExecArray | null;

  while ((match = fenceRegex.exec(normalized)) !== null) {
    const idx = match.index;
    const before = normalized.slice(lastIndex, idx);
    if (before) {
      // Replace single newlines (not followed by another newline) with Markdown hardbreaks
      parts.push(before.replace(/\n(?!\n)/g, '  \n'));
    }
    parts.push(match[0]); // code fence unchanged
    lastIndex = idx + match[0].length;
  }

  const rest = normalized.slice(lastIndex);
  if (rest) parts.push(rest.replace(/\n(?!\n)/g, '  \n'));

  return parts.join('');
}

export default TypewriterMarkdown;
