import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';

interface KeywordHighlighterProps {
  text: string;
  keywords: string[];
  className?: string;
}

const KeywordHighlighter: React.FC<KeywordHighlighterProps> = ({ text, keywords, className }) => {
  const highlightedText = useMemo(() => {
    if (!keywords || keywords.length === 0 || !text) {
      return text;
    }
    const sortedKeywords = [...keywords].sort((a, b) => b.length - a.length);
    let highlightMap = new Map<number, { isStart: boolean; keyword: string }>();
    sortedKeywords.forEach(keyword => {
      if (!keyword.trim()) return;

      const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
      let match;
      
      while ((match = regex.exec(text)) !== null) {
        const start = match.index;
        const end = start + match[0].length;
        
        let overlaps = false;
        highlightMap.forEach((value, position) => {
          if ((position >= start && position < end) || 
              (value.isStart === false && start >= position - value.keyword.length && start < position)) {
            overlaps = true;
          }
        });
        
        if (!overlaps) {
          highlightMap.set(start, { isStart: true, keyword });
          highlightMap.set(end, { isStart: false, keyword });
        }
      }
    });

    if (highlightMap.size === 0) {
      return text;
    }
    
    const positions = Array.from(highlightMap.keys()).sort((a, b) => a - b);
    
    let result = [];
    let lastPos = 0;
    let openTags = 0;
    
    positions.forEach(pos => {
      const info = highlightMap.get(pos)!;
      
      if (pos > lastPos) {
        result.push(text.substring(lastPos, pos));
      }
      
      if (info.isStart) {
        result.push('<span class="highlighted-keyword">');
        openTags++;
      } else {
        result.push('</span>');
        openTags--;
      }
      
      lastPos = pos;
    });
    
    if (lastPos < text.length) {
      result.push(text.substring(lastPos));
    }
    
    while (openTags > 0) {
      result.push('</span>');
      openTags--;
    }
    
    return result.join('');
  }, [text, keywords]);
  
  return (
    <pre 
      className={cn("whitespace-pre-wrap", className)} 
      dangerouslySetInnerHTML={{ __html: highlightedText }}
    />
  );
};

export default KeywordHighlighter; 