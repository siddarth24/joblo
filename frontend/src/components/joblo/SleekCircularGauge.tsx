import React from 'react';

interface SleekCircularGaugeProps {
  score: number;
  size?: number;
  strokeWidth?: number;
}

const SleekCircularGauge: React.FC<SleekCircularGaugeProps> = ({ 
  score, 
  size = 100, 
  strokeWidth = 4 
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  
  // Dynamic color based on score
  const getScoreColor = () => {
    if (score >= 85) return 'rgb(16, 185, 129)'; // Green
    if (score >= 70) return 'rgb(14, 165, 233)'; // Blue
    if (score >= 50) return 'rgb(250, 204, 21)'; // Yellow
    return 'rgb(239, 68, 68)'; // Red
  };
  
  // Dynamic background glow based on score
  const getGlowColor = () => {
    if (score >= 85) return 'rgba(16, 185, 129, 0.2)';
    if (score >= 70) return 'rgba(14, 165, 233, 0.2)';
    if (score >= 50) return 'rgba(250, 204, 21, 0.2)';
    return 'rgba(239, 68, 68, 0.2)';
  };

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      {/* Background glow */}
      <div 
        className="absolute rounded-full animate-pulse" 
        style={{ 
          width: size * 0.9, 
          height: size * 0.9, 
          backgroundColor: getGlowColor(),
          filter: 'blur(10px)'
        }}
      ></div>
      
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        {/* Background circle */}
        <circle 
          className="text-white/5" 
          strokeWidth={strokeWidth} 
          stroke="currentColor" 
          fill="transparent" 
          r={radius} 
          cx={size / 2} 
          cy={size / 2} 
        />
        
        {/* Progress circle with gradient */}
        <circle 
          className="transition-all duration-1000 ease-out" 
          strokeWidth={strokeWidth} 
          strokeDasharray={circumference} 
          strokeDashoffset={offset} 
          strokeLinecap="round" 
          stroke={getScoreColor()}
          fill="transparent" 
          r={radius} 
          cx={size / 2} 
          cy={size / 2} 
        />
      </svg>
      
      {/* Score text */}
      <div className="absolute flex flex-col items-center justify-center text-center">
        <span className="text-xl font-medium text-white">{score}</span>
        <span className="text-[9px] text-white/50 uppercase tracking-wider mt-[-4px]">pts</span>
      </div>
    </div>
  );
};

export default SleekCircularGauge; 