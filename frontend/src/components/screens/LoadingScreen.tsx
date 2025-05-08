import React from 'react';
import { Brain } from 'lucide-react';

interface LoadingScreenProps {
  isLoading: boolean;
  loadingMessage: string;
}

const LoadingScreen: React.FC<LoadingScreenProps> = ({ isLoading, loadingMessage }) => {
  return (
    <div 
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-black/80 backdrop-blur-md p-4 transition-opacity duration-500 ease-in-out" 
      style={{ opacity: isLoading ? 1 : 0, visibility: isLoading ? 'visible' : 'hidden' }}
    >
      <div className="aurora-bg">
        <div className="aurora-gradient aurora-g1"></div>
        <div className="aurora-gradient aurora-g2"></div>
        <div className="aurora-gradient aurora-g3"></div>
      </div>
      
      <div className="glass-card p-10 rounded-xl relative z-10 w-full max-w-sm text-center animate-fade-in border border-white/10 shadow-glow">
        <div className="relative flex justify-center mb-8">
          <div className="absolute w-24 h-24 rounded-full bg-cyan-500/5"></div>
          <div className="absolute w-28 h-28 rounded-full border border-cyan-500/5 animate-ping opacity-70"></div>
          <div className="absolute w-20 h-20 rounded-full border-2 border-transparent border-t-cyan-500/20 border-r-cyan-500/10 animate-spin-medium"></div>
          <div className="absolute w-16 h-16 rounded-full border border-transparent border-b-cyan-400/30 animate-spin-slow" style={{animationDirection: 'reverse'}}></div>
          <div className="absolute w-10 h-10 rounded-full bg-gradient-to-br from-cyan-500/10 to-blue-500/10 animate-pulse"></div>
          <Brain className="w-6 h-6 text-cyan-400/90" />
        </div>
        
        <h2 className="text-lg font-medium text-white animate-pulse">{loadingMessage}</h2>
        <p className="mt-2 text-xs text-white/40">Neural processing in progress</p>
        
        <div className="mt-8 w-full h-1 bg-white/5 rounded-full overflow-hidden">
          <div className="h-full w-1/2 bg-gradient-to-r from-cyan-500 to-blue-500 animate-pulse"></div>
        </div>
        
        <div className="mt-6 flex justify-center">
          <div className="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoadingScreen; 