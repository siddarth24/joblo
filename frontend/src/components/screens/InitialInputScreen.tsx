import React, { ChangeEvent, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@radix-ui/react-label';
import { Briefcase, FileText, LinkIcon, Type, Paperclip, XCircle, CheckCircle2, Send } from 'lucide-react';
import { cn } from '@/lib/utils';
import NecktieIcon from '../icons/NecktieIcon';

type JobInputUIMode = 'link' | 'text';
type AppStep = 'initial_input' | 'optional_kb_upload' | 'loading' | 'results_job_data' | 'results_cv_preview' | 'results_ats_original' | 'results_resume_preview' | 'error';

interface InitialInputScreenProps {
  jobInputUIMode: JobInputUIMode;
  setJobInputUIMode: (mode: JobInputUIMode) => void;
  jobUrl: string;
  setJobUrl: (url: string) => void;
  jobDescription: string;
  setJobDescription: (desc: string) => void;
  resumeFile: File | null;
  handleAttachResumeClick: () => void;
  removeResumeFile: () => void;
  canSubmitInitial: boolean;
  proceedToKbUpload: () => void;
  appStep: AppStep;
  hiddenResumeInputRef: React.RefObject<HTMLInputElement | null>;
  handleResumeFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
}

const InitialInputScreen = React.memo<InitialInputScreenProps>(({
  jobInputUIMode, setJobInputUIMode, jobUrl, setJobUrl, jobDescription, setJobDescription,
  resumeFile, handleAttachResumeClick, removeResumeFile, canSubmitInitial, proceedToKbUpload,
  appStep, hiddenResumeInputRef, handleResumeFileChange
}) => {
  // Refs for inputs should be defined inside the component that owns the DOM elements
  const jobUrlInputRef = useRef<HTMLInputElement>(null);
  const jobDescriptionRef = useRef<HTMLTextAreaElement>(null);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-gradient-to-b from-[#050a14] to-black relative overflow-hidden">
      <div className="aurora-bg">
        <div className="aurora-gradient aurora-g1"></div>
        <div className="aurora-gradient aurora-g2"></div>
        <div className="aurora-gradient aurora-g3"></div>
      </div>
      
      <div className="w-full max-w-md relative z-10 animate-fade-in">
        <div className="glass-card p-8 rounded-xl border border-white/10 shadow-glow">
          <div className="flex flex-col items-center mb-8 relative">
            <div className="relative mb-4">
              <NecktieIcon className="h-12 w-12 text-cyan-400" strokeWidth={1.5} />
              <div className="absolute inset-0 bg-cyan-400/20 blur-xl rounded-full -z-10"></div>
            </div>
            <h1 className="text-3xl font-medium text-white mb-1">
              Joblo<span className="text-gradient font-semibold">AI</span>
            </h1>
            <p className="text-sm text-white/50">Your AI-powered resume optimizer</p>
          </div>
          
          <div className="space-y-6 animate-slide-up">
            <div className="relative flex w-full rounded-lg border border-white/10 p-0.5 bg-white/5">
              <span 
                className={cn(
                  "absolute top-0.5 bottom-0.5 left-0.5 w-[calc(50%-2px)] rounded-md bg-gradient-to-r from-cyan-500/80 to-blue-500/80 transition-transform duration-300 ease-out",
                  jobInputUIMode === 'text' ? 'translate-x-full' : 'translate-x-0'
                )} 
                aria-hidden="true" 
              />
              <Button 
                onClick={() => setJobInputUIMode('link')} 
                variant="ghost" 
                size="sm" 
                className={cn(
                  "flex-1 py-2 rounded-md text-sm z-10 transition-colors",
                  jobInputUIMode === 'link' ? 'text-white font-medium' : 'text-white/50'
                )}
              >
                <LinkIcon className="mr-1.5 h-4 w-4" /> URL
              </Button>
              <Button 
                onClick={() => setJobInputUIMode('text')} 
                variant="ghost" 
                size="sm" 
                className={cn(
                  "flex-1 py-2 rounded-md text-sm z-10 transition-colors",
                  jobInputUIMode === 'text' ? 'text-white font-medium' : 'text-white/50'
                )}
              >
                <Type className="mr-1.5 h-4 w-4" /> Text
              </Button>
            </div>
            
            {jobInputUIMode === 'link' ? (
              <div className="space-y-2">
                <Label className="text-sm text-white/70 flex items-center">
                  <Briefcase className="h-3 w-3 mr-1.5 opacity-70" />
                  Job URL
                </Label>
                <div className="relative">
                  <Input 
                    ref={jobUrlInputRef}
                    type="url" 
                    placeholder="https://example.com/job" 
                    value={jobUrl} 
                    onChange={(e) => setJobUrl(e.target.value)}
                    className="futuristic-input bg-white/5 border-white/10 text-white focus:border-cyan-500/40 focus-visible:ring-1 focus-visible:ring-cyan-500/30 pl-9" 
                  />
                  <LinkIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-white/30" />
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <Label className="text-sm text-white/70 flex items-center">
                  <Briefcase className="h-3 w-3 mr-1.5 opacity-70" />
                  Job Description
                </Label>
                <Textarea 
                  ref={jobDescriptionRef}
                  placeholder="Paste job description..." 
                  value={jobDescription} 
                  onChange={(e) => setJobDescription(e.target.value)}
                  className="futuristic-input bg-white/5 border-white/10 text-white focus:border-cyan-500/40 min-h-[140px] resize-none modern-scrollbar"
                />
              </div>
            )}
            
            <div className="space-y-2">
              <Label className="text-sm text-white/70 flex items-center">
                <FileText className="h-3 w-3 mr-1.5 opacity-70" />
                Resume
              </Label>
              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  onClick={handleAttachResumeClick} 
                  className={cn(
                    "w-full justify-start text-sm bg-white/5 border-white/10 text-white/80 hover:bg-white/10 hover:text-white transition-colors h-11 pl-4",
                    resumeFile && "border-cyan-500/30 bg-cyan-500/5"
                  )}
                >
                  {resumeFile ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 mr-2 text-cyan-400" />
                      <span className="truncate max-w-[220px]">{resumeFile.name}</span>
                    </>
                  ) : (
                    <>
                      <Paperclip className="h-4 w-4 mr-2 opacity-70" />
                      Attach Resume (PDF, DOCX)
                    </>
                  )}
                </Button>
                {resumeFile && (
                  <Button 
                    variant="ghost" 
                    onClick={removeResumeFile} 
                    className="h-11 w-11 text-white/40 hover:text-red-400 hover:bg-red-500/10 rounded-md p-0 border border-transparent"
                  >
                    <XCircle className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
            
            <Button 
              onClick={proceedToKbUpload} 
              disabled={!canSubmitInitial || appStep === 'loading'} 
              className={cn(
                "w-full py-6 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white font-medium transition-all shadow-glow-primary rounded-lg",
                !canSubmitInitial && "opacity-50 shadow-none from-neutral-700 to-neutral-800 hover:from-neutral-700 hover:to-neutral-800"
              )}
            >
              Continue
              <Send className="ml-2 h-4 w-4" />
            </Button>
            
            <input type="file" ref={hiddenResumeInputRef} onChange={handleResumeFileChange} className="hidden" accept=".pdf,.doc,.docx,.txt" />
          </div>
        </div>
      </div>
    </div>
  );
});

InitialInputScreen.displayName = 'InitialInputScreen'; // For better debugging

export default InitialInputScreen;