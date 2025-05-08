import React from 'react';
import { ArrowLeft, Send, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { cn } from "@/lib/utils";

interface ResultsDisplayCardProps {
  title: string;
  icon: React.ElementType;
  description?: string;
  children: React.ReactNode;
  nextAction?: () => void;
  nextActionLabel?: string;
  prevAction?: () => void;
  prevActionLabel?: string;
  isLoadingNext?: boolean;
}

const ResultsDisplayCard: React.FC<ResultsDisplayCardProps> = ({
  title,
  icon: Icon,
  description,
  children,
  nextAction,
  nextActionLabel,
  prevAction,
  prevActionLabel,
  isLoadingNext
}) => (
  <Card className="glass-card w-full max-w-3xl mx-auto transition-all duration-300 ease-in-out animate-fade-in card-hover-effect">
    <CardHeader className="pb-4 border-b border-white/5">
      <div className="flex items-center justify-between">
        <CardTitle className="flex items-center text-xl text-white">
          <div className="relative mr-3">
            <Icon className="h-5 w-5 text-cyan-400" />
            <div className="absolute inset-0 bg-cyan-400/20 blur-sm rounded-full -z-10 scale-150"></div>
          </div>
          {title}
        </CardTitle>
        {prevAction && (
          <Button 
            variant="outline" 
            size="sm" 
            onClick={prevAction} 
            className="border-white/10 text-white/60 bg-white/5 hover:bg-white/10 hover:text-white transition-colors"
          >
            <ArrowLeft className="mr-1.5 h-4 w-4" /> {prevActionLabel || "Back"}
          </Button>
        )}
      </div>
      {description && <CardDescription className="text-white/50 pt-1">{description}</CardDescription>}
    </CardHeader>
    
    <CardContent className="text-white/80 py-5 animate-slide-up">
      {children}
    </CardContent>
    
    {nextAction && nextActionLabel && (
      <CardFooter className="flex justify-end pt-4 border-t border-white/5">
        <Button 
          onClick={nextAction} 
          disabled={isLoadingNext} 
          className={cn(
            "text-white bg-gradient-to-r from-cyan-500 to-blue-500 hover:opacity-90 transition-all", 
            isLoadingNext && "opacity-60 cursor-not-allowed"
          )}
        >
          {isLoadingNext ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {nextActionLabel} <Send className="ml-2 h-4 w-4" />
        </Button>
      </CardFooter>
    )}
  </Card>
);

export default ResultsDisplayCard; 