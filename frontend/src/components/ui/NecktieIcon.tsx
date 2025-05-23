import React from 'react';

interface NecktieIconProps {
  width?: string | number;
  height?: string | number; 
  strokeWidth?: string | number;
  className?: string;
  color?: string;
  animate?: boolean; 
  glowEffect?: boolean; 
  gradientColors?: {  
    start?: string;
    middle?: string;
    end?: string;
  };
  [key: string]: any; 
}

const NecktieIcon: React.FC<NecktieIconProps> = ({
  width = "24",
  height = "24", 
  strokeWidth = "1.5",
  className = "",
  color = "currentColor",
  animate, 
  glowEffect, 
  gradientColors, 
  ...props
}) => {
  const domProps = { ...props };
  
  const glowOpacity = glowEffect ? "0.3" : "0.2";
  
  const iconColor = gradientColors ? gradientColors.middle || color : color;

  return (
    <div className="relative inline-flex items-center justify-center">
      <div 
        className="absolute inset-0 rounded-full blur-md"
        style={{ 
          backgroundColor: iconColor,
          opacity: glowOpacity
        }}
      ></div>
      
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width={width}
        height={height}
        viewBox="0 0 24 24"
        fill="none"
        stroke={iconColor}
        strokeWidth={strokeWidth}
        className={`necktie-icon relative z-10 ${className}`}
        {...domProps}
      >
        <path 
          d="M8.5 2C8.5 2 8 4 9 4H15C16 4 15.5 2 15.5 2H8.5Z" 
          fill="none"
        />
        
        <path 
          d="M9 4L6.5 20L12 23L17.5 20L15 4H9Z" 
          fill="none"
        />
        
        <path 
          d="M9.5 4.5L12 6L14.5 4.5" 
          strokeOpacity="0.9"
          strokeWidth={strokeWidth ? parseFloat(strokeWidth.toString()) / 1.5 : 1}
        />
      </svg>
    </div>
  );
};

export default NecktieIcon; 