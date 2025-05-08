import React from 'react';
import { TrendingUp, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import SleekCircularGauge from './SleekCircularGauge';

interface AtsScore {
  score: number;
  summary: string;
  recommendations: string[] | string;
}

interface AtsScoreResultDisplayProps {
  scoreData: AtsScore | null;
  titlePrefix: string;
  comparisonScore?: number | null;
  onCopy: (text: string | undefined | null, type: string) => void;
}

const AtsScoreResultDisplay: React.FC<AtsScoreResultDisplayProps> = ({ 
  scoreData, 
  titlePrefix, 
  comparisonScore,
  onCopy 
}) => {
  if (!scoreData) return <p className="text-white/60 text-center py-4">ATS data unavailable</p>;
  
  const { score, summary, recommendations } = scoreData;
  const scoreDiff = comparisonScore !== undefined && comparisonScore !== null ? score - comparisonScore : null;
  const percentageImprovement = comparisonScore && comparisonScore > 0 && scoreDiff !== null ? ((scoreDiff / comparisonScore) * 100).toFixed(0) : null;
  const recommendationText = typeof recommendations === 'string' ? recommendations : recommendations.join('\n');

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
        <div className="flex-shrink-0 relative">
          <SleekCircularGauge score={score} size={110} strokeWidth={4} />
          
          {scoreDiff !== null && scoreDiff > 0 && (
            <div className="absolute -bottom-1 -right-1 flex items-center bg-emerald-500/90 text-white text-xs font-medium px-2 py-0.5 rounded-full animate-pulse">
              <TrendingUp className="h-3 w-3 mr-1"/> 
              <span>+{scoreDiff}</span>
              {percentageImprovement && (
                <span className="text-[10px] ml-1 bg-white/20 rounded px-1">{percentageImprovement}%</span>
              )}
            </div>
          )}
          
          {scoreDiff !== null && scoreDiff < 0 && (
            <div className="absolute -bottom-1 -right-1 flex items-center bg-red-500/90 text-white text-xs font-medium px-1.5 py-0.5 rounded-full">
              {scoreDiff} pts
            </div>
          )}
        </div>
        
        <div className="flex-grow text-center sm:text-left">
          <h4 className="text-base font-medium text-white mb-2 flex items-center justify-center sm:justify-start group">
            {titlePrefix} Summary
            <Button 
              variant="ghost" 
              size="icon" 
              className="ml-1 h-7 w-7 text-white/30 opacity-0 group-hover:opacity-100 hover:text-cyan-400 hover:bg-cyan-400/10 transition-all" 
              onClick={() => onCopy(summary, 'Summary')}
            >
              <Copy className="h-3.5 w-3.5"/>
            </Button>
          </h4>
          
          <div className="frost-glass p-3 rounded-md">
            <p className="text-sm text-white/80">{summary}</p>
          </div>
        </div>
      </div>
      
      <div className="space-y-2">
        <h4 className="text-base font-medium text-white mb-2 flex items-center group">
          Recommendations
          <Button 
            variant="ghost" 
            size="icon" 
            className="ml-1 h-7 w-7 text-white/30 opacity-0 group-hover:opacity-100 hover:text-cyan-400 hover:bg-cyan-400/10 transition-all" 
            onClick={() => onCopy(recommendationText, 'Recommendations')}
          >
            <Copy className="h-3.5 w-3.5"/>
          </Button>
        </h4>
        
        <div className="frost-glass p-3 rounded-md">
          {typeof recommendations === 'string' ? (
            <p className="text-sm text-white/80">{recommendations}</p>
          ) : (
            <ul className="list-disc list-inside text-sm text-white/80 space-y-1">
              {recommendations.map((rec, i) => (
                <li key={i} className="py-0.5">{rec}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};

export default AtsScoreResultDisplay; 