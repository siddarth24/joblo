import React from 'react';
import { AlertTriangle, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ErrorScreenProps {
  isError: boolean;
  resetApp: () => void;
}

const ErrorScreen: React.FC<ErrorScreenProps> = ({ isError, resetApp }) => {
  return (
    <div 
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-black/90 backdrop-blur-md p-4 transition-opacity duration-500 ease-in-out" 
      style={{ opacity: isError ? 1 : 0, visibility: isError ? 'visible' : 'hidden' }}
    >
      <div className="aurora-bg opacity-30">
        <div className="aurora-gradient aurora-g1"></div>
        <div className="aurora-gradient aurora-g2"></div>
      </div>
      <div className="bg-neutral-950/80 p-8 rounded-xl border border-red-900/30 shadow-xl relative z-10 w-full max-w-sm text-center">
        <AlertTriangle className="w-12 h-12 text-red-500/90 mx-auto" />
        <h2 className="mt-5 text-lg font-medium text-white">Error</h2>
        <p className="mt-2 text-sm text-neutral-400 mb-6">An unexpected error occurred while processing your request.</p>
        <Button 
          onClick={resetApp} 
          className="bg-neutral-800 hover:bg-neutral-700 text-white transition-colors"
        >
          <ArrowLeft className="mr-2 h-4 w-4" /> Return to Start
        </Button>
      </div>
    </div>
  );
};

export default ErrorScreen; 