import React from 'react';
import { Brain } from 'lucide-react';

const FuturisticLoader = () => (
  <div className="relative w-20 h-20 flex items-center justify-center">
    <div className="absolute w-full h-full rounded-full border-2 border-transparent border-t-cyan-500/30 border-r-cyan-400/20 animate-spin-medium"></div>
    <div className="absolute w-14 h-14 rounded-full border-2 border-transparent border-b-cyan-400/40 border-l-cyan-500/20 animate-spin-slow" style={{animationDirection: 'reverse'}}></div>
    <div className="absolute w-8 h-8 rounded-full border border-cyan-400/50 animate-pulse"></div>
    <Brain className="w-5 h-5 text-cyan-400" />
  </div>
);

export default FuturisticLoader; 