import React from 'react';
import { AppStep } from '@/types';
import { cn } from '@/lib/utils';
import { CheckCircle2, Circle } from 'lucide-react';

interface ProgressStepperProps {
  currentStep: AppStep;
  className?: string;
}

const steps: { key: AppStep; label: string }[] = [
  { key: 'initial_input', label: 'Input' },
  { key: 'optional_kb_upload', label: 'Context' },
  { key: 'results_job_data', label: 'Job Analysis' },
  { key: 'results_cv_preview', label: 'Resume' },
  { key: 'results_ats_original', label: 'ATS Score' },
  { key: 'results_resume_preview', label: 'Optimized' }
];

const ProgressStepper: React.FC<ProgressStepperProps> = ({ currentStep, className }) => {
  // Get the numeric index of the current step
  const currentIndex = steps.findIndex(step => {
    if (currentStep === 'loading') {
      return false; // Special handling for loading state
    }
    if (currentStep === 'error') {
      return false; // Special handling for error state
    }
    return step.key === currentStep;
  });

  return (
    <div className={cn("w-full py-3 px-4 flex items-center justify-center", className)}>
      <div className="flex items-center justify-between max-w-2xl w-full relative">
        {/* Progress line */}
        <div className="absolute left-0 right-0 top-1/2 h-0.5 bg-white/10 -translate-y-1/2 z-0"></div>
        
        {/* Active progress line */}
        <div 
          className="absolute left-0 top-1/2 h-0.5 bg-gradient-to-r from-cyan-500 to-blue-500 -translate-y-1/2 z-0 transition-all duration-500"
          style={{ 
            width: `${Math.max((currentIndex / (steps.length - 1)) * 100, 0)}%`,
          }}
        ></div>
        
        {/* Steps */}
        {steps.map((step, index) => {
          const isCompleted = currentIndex > index;
          const isCurrent = currentIndex === index;
          const isUpcoming = currentIndex < index;
          
          return (
            <div 
              key={step.key} 
              className={cn(
                "flex flex-col items-center relative z-10 transition-all duration-300",
                isCompleted && "opacity-90",
                isCurrent && "opacity-100",
                isUpcoming && "opacity-40"
              )}
            >
              <div className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center transition-all duration-500",
                isCompleted ? "bg-cyan-500/80" : isCurrent ? "bg-white/10 border border-cyan-500/80" : "bg-white/5 border border-white/20"
              )}>
                {isCompleted ? (
                  <CheckCircle2 className="w-5 h-5 text-white" />
                ) : (
                  <Circle className={cn("w-2 h-2", isCurrent ? "text-cyan-400" : "text-white/30")} fill={isCurrent ? "currentColor" : "none"} />
                )}
              </div>
              <span className={cn(
                "mt-1.5 text-xs font-medium transition-all duration-300",
                isCompleted ? "text-cyan-400" : isCurrent ? "text-white" : "text-white/50"
              )}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ProgressStepper; 