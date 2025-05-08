import React from 'react';

interface QuantumSpinnerProps {
  size?: string;
  className?: string;
}

const QuantumSpinner: React.FC<QuantumSpinnerProps> = ({ 
  size = '120px', 
  className = '' 
}) => {
  return (
    <div className={`quantum-spinner ${className}`} style={{width: size, height: size}}>
      <div className="quantum-spinner__ring quantum-spinner__ring--1"></div>
      <div className="quantum-spinner__ring quantum-spinner__ring--2"></div>
      <div className="quantum-spinner__ring quantum-spinner__ring--3"></div>
      <div className="quantum-spinner__core"></div>
      <div className="quantum-spinner__particle"></div>
      <div className="quantum-spinner__particle"></div>
      <div className="quantum-spinner__particle"></div>
      <div className="quantum-spinner__particle"></div>
    </div>
  );
};

export default QuantumSpinner; 