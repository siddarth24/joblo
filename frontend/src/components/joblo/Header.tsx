import React from 'react';
import { Github, Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';
import NecktieIcon from '../icons/NecktieIcon';

const Header: React.FC = () => {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/5 bg-black/60 backdrop-blur supports-backdrop-blur:bg-black/40">
      <div className="container flex h-16 items-center justify-between max-w-5xl mx-auto px-4">
        <div className="flex items-center">
          <div className="relative mr-2">
            <NecktieIcon className="h-6 w-6 text-cyan-400" strokeWidth={1.5} />
            <div className="absolute inset-0 bg-cyan-400/20 blur-md rounded-full -z-10"></div>
          </div>
          <h1 className="text-xl font-medium text-white">Joblo<span className="text-gradient font-semibold">AI</span></h1>
          <div className="ml-3 px-2 py-0.5 rounded-full text-[10px] font-medium border border-cyan-500/20 bg-cyan-500/5 text-cyan-400">v1.0</div>
        </div>
        <div className="flex items-center space-x-2">
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="text-white/50 hover:text-cyan-400 hover:bg-cyan-400/10 transition-all rounded-full h-9 w-9" 
                  onClick={() => window.open("https://github.com/your-repo/joblo-extension", "_blank")}
                >
                  <Github className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent className="glass-card text-white border-none">
                <p>View on GitHub</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          
          <Separator orientation="vertical" className="h-6 bg-white/5"/>
          
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="text-white/50 hover:text-cyan-400 hover:bg-cyan-400/10 transition-all rounded-full h-9 w-9" 
                >
                  <Settings2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent className="glass-card text-white border-none">
                <p>Settings</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>
    </header>
  );
};

export default Header; 