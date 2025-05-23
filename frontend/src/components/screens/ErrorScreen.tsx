import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button, MotionButton } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { motion } from 'framer-motion';

interface ErrorScreenProps {
  isError: boolean;
  resetApp: () => void;
}

const ErrorScreen: React.FC<ErrorScreenProps> = ({ isError, resetApp }) => {
  return (
    <div 
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center p-6 transition-opacity duration-500 ease-in-out" 
      style={{ opacity: isError ? 1 : 0, visibility: isError ? 'visible' : 'hidden' }}
    >
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-[40%] -left-[20%] w-[80%] h-[70%] rounded-full bg-destructive/5 blur-3xl"></div>
        <div className="absolute -bottom-[40%] -right-[20%] w-[80%] h-[70%] rounded-full bg-primary/5 blur-3xl"></div>
      </div>
      
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md relative z-10"
      >
        <Card variant="glass" className="backdrop-blur-xl border-destructive/20">
          <CardHeader className="pb-4">
            <div className="mx-auto w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
              <AlertCircle className="h-6 w-6 text-destructive" />
            </div>
            <CardTitle className="text-center">Something went wrong</CardTitle>
            <CardDescription className="text-center">
              We encountered an error while processing your request. This might be due to server issues or data validation problems.
            </CardDescription>
          </CardHeader>
          
          <CardContent>
            <p className="text-sm text-center text-muted-foreground">
              You can try refreshing the page or starting a new session.
            </p>
          </CardContent>
          
          <CardFooter className="flex justify-center pb-6">
            <MotionButton 
              variant="default" 
              onClick={resetApp}
              className="px-6"
            >
              <RefreshCw className="mr-2 h-4 w-4" /> 
              Try Again
            </MotionButton>
          </CardFooter>
        </Card>
      </motion.div>
    </div>
  );
};

export default ErrorScreen; 