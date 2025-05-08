import React, { ChangeEvent, useRef, useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@radix-ui/react-label';
import { 
  Briefcase, FileText, LinkIcon, Type, Paperclip, XCircle, 
  CheckCircle2, Send, Info, AlertCircle 
} from 'lucide-react';
import { cn } from '@/lib/utils';
import NecktieIcon from '../icons/NecktieIcon';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { motion, AnimatePresence } from 'framer-motion';

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
  
  // Validation states
  const [urlTouched, setUrlTouched] = useState(false);
  const [descriptionTouched, setDescriptionTouched] = useState(false);
  
  // Derived validation states
  const isUrlValid = 
    !urlTouched || 
    (jobUrl.trim() === '') || 
    (jobUrl.trim().startsWith('http://') || jobUrl.trim().startsWith('https://'));

  const isDescriptionValid = 
    !descriptionTouched || 
    jobDescription.trim() === '' || 
    jobDescription.trim().length > 20;

  // Focus the active input when mode changes
  useEffect(() => {
    // Small delay to ensure DOM elements are ready after mode switch
    const timeoutId = setTimeout(() => {
      if (jobInputUIMode === 'link' && jobUrlInputRef.current) {
        jobUrlInputRef.current.focus();
      } else if (jobInputUIMode === 'text' && jobDescriptionRef.current) {
        jobDescriptionRef.current.focus();
      }
    }, 100);

    return () => clearTimeout(timeoutId);
  }, [jobInputUIMode]);

  // Animation variants
  const containerVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { 
      opacity: 1, 
      y: 0, 
      transition: { 
        duration: 0.5,
        staggerChildren: 0.1,
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 10 },
    visible: { opacity: 1, y: 0 }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-gradient-to-b from-[#050a14] to-black relative overflow-hidden">
      <div className="aurora-bg" aria-hidden="true">
        <div className="aurora-gradient aurora-g1"></div>
        <div className="aurora-gradient aurora-g2"></div>
        <div className="aurora-gradient aurora-g3"></div>
      </div>
      
      <motion.div 
        className="w-full max-w-md relative z-10"
        initial="hidden"
        animate="visible"
        variants={containerVariants}
      >
        <div className="glass-card p-8 rounded-xl border border-white/10 shadow-glow">
          <motion.div 
            className="flex flex-col items-center mb-8 relative"
            variants={itemVariants}
          >
            <div className="relative mb-4">
              <NecktieIcon className="h-12 w-12 text-cyan-400" strokeWidth={1.5} />
              <div className="absolute inset-0 bg-cyan-400/20 blur-xl rounded-full -z-10"></div>
            </div>
            <h1 className="text-3xl font-medium text-white mb-1">
              Joblo<span className="text-gradient font-semibold">AI</span>
            </h1>
            <p className="text-sm text-white/50">Your AI-powered resume optimizer</p>
          </motion.div>
          
          <div className="space-y-6">
            <motion.div 
              className="relative flex w-full rounded-lg border border-white/10 p-0.5 bg-white/5"
              variants={itemVariants}
            >
              <span 
                className={cn(
                  "absolute top-0.5 bottom-0.5 left-0.5 w-[calc(50%-2px)] rounded-md bg-gradient-to-r from-cyan-500/80 to-blue-500/80 transition-transform duration-300 ease-out-expo",
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
                aria-pressed={jobInputUIMode === 'link'}
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
                aria-pressed={jobInputUIMode === 'text'}
              >
                <Type className="mr-1.5 h-4 w-4" /> Text
              </Button>
            </motion.div>
            
            <AnimatePresence mode="wait">
              {jobInputUIMode === 'link' ? (
                <motion.div 
                  key="url-input"
                  className="space-y-2"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  variants={itemVariants}
                >
                  <div className="flex justify-between">
                    <Label htmlFor="job-url" className="text-sm text-white/70 flex items-center">
                      <Briefcase className="h-3 w-3 mr-1.5 opacity-70" />
                      Job URL
                    </Label>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-5 w-5 text-white/40 hover:text-white/70">
                            <Info className="h-3 w-3" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent className="bg-slate-900 border-slate-800 text-white text-xs px-2 py-1">
                          <p>Paste the URL of the job posting</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <div className="relative">
                    <Input 
                      id="job-url"
                      ref={jobUrlInputRef}
                      type="url" 
                      placeholder="https://example.com/job" 
                      value={jobUrl} 
                      onChange={(e) => setJobUrl(e.target.value)}
                      onBlur={() => setUrlTouched(true)}
                      aria-invalid={!isUrlValid}
                      className={cn(
                        "futuristic-input bg-white/5 border-white/10 text-white focus:border-cyan-500/40 focus-visible:ring-1 focus-visible:ring-cyan-500/30 pl-9",
                        !isUrlValid && "border-red-500/50 focus:border-red-500/50"
                      )}
                    />
                    <LinkIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-white/30" />
                    {!isUrlValid && (
                      <div className="flex items-center mt-1 text-red-400 text-xs">
                        <AlertCircle className="h-3 w-3 mr-1" />
                        URL must start with http:// or https://
                      </div>
                    )}
                  </div>
                </motion.div>
              ) : (
                <motion.div 
                  key="description-input"
                  className="space-y-2"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  variants={itemVariants}
                >
                  <div className="flex justify-between">
                    <Label htmlFor="job-description" className="text-sm text-white/70 flex items-center">
                      <Briefcase className="h-3 w-3 mr-1.5 opacity-70" />
                      Job Description
                    </Label>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-5 w-5 text-white/40 hover:text-white/70">
                            <Info className="h-3 w-3" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent className="bg-slate-900 border-slate-800 text-white text-xs px-2 py-1">
                          <p>Paste the full job description text</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <div className="relative">
                    <Textarea 
                      id="job-description"
                      ref={jobDescriptionRef}
                      placeholder="Paste job description..." 
                      value={jobDescription} 
                      onChange={(e) => setJobDescription(e.target.value)}
                      onBlur={() => setDescriptionTouched(true)}
                      aria-invalid={!isDescriptionValid}
                      className={cn(
                        "futuristic-input bg-white/5 border-white/10 text-white focus:border-cyan-500/40 min-h-[140px] resize-none modern-scrollbar",
                        !isDescriptionValid && "border-red-500/50 focus:border-red-500/50"
                      )}
                    />
                    {!isDescriptionValid && (
                      <div className="flex items-center mt-1 text-red-400 text-xs">
                        <AlertCircle className="h-3 w-3 mr-1" />
                        Job description must be at least 20 characters
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            
            <motion.div 
              className="space-y-2"
              variants={itemVariants}
            >
              <div className="flex justify-between">
                <Label htmlFor="resume-upload" className="text-sm text-white/70 flex items-center">
                  <FileText className="h-3 w-3 mr-1.5 opacity-70" />
                  Resume
                </Label>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-5 w-5 text-white/40 hover:text-white/70">
                        <Info className="h-3 w-3" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent className="bg-slate-900 border-slate-800 text-white text-xs px-2 py-1">
                      <p>Upload your current resume (PDF or DOCX)</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  onClick={handleAttachResumeClick} 
                  id="resume-upload"
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
                    size="icon" 
                    onClick={removeResumeFile} 
                    className="h-11 w-11 text-white/40 hover:text-red-400 hover:bg-red-500/10 rounded-lg"
                    aria-label="Remove resume file"
                  >
                    <XCircle className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </motion.div>
            
            <motion.div variants={itemVariants}>
              <Button 
                onClick={proceedToKbUpload} 
                disabled={!canSubmitInitial || appStep === 'loading'} 
                className={cn(
                  "w-full py-6 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white font-medium transition-all shadow-glow-primary rounded-lg",
                  !canSubmitInitial && "opacity-50 shadow-none from-neutral-700 to-neutral-800 hover:from-neutral-700 hover:to-neutral-800"
                )}
                whileHover={{ scale: canSubmitInitial ? 1.02 : 1 }}
                whileTap={{ scale: canSubmitInitial ? 0.98 : 1 }}
              >
                Continue
                <Send className="ml-2 h-4 w-4" />
              </Button>
            </motion.div>
            
            <input 
              type="file" 
              ref={hiddenResumeInputRef} 
              onChange={handleResumeFileChange} 
              className="hidden" 
              accept=".pdf,.doc,.docx,.txt"
              aria-hidden="true" 
            />
          </div>
        </div>
      </motion.div>

      <motion.div 
        className="mt-6 text-xs text-white/40 text-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1, transition: { delay: 0.8 } }}
      >
        <p>Your files are processed securely and confidentially</p>
      </motion.div>
    </div>
  );
});

InitialInputScreen.displayName = 'InitialInputScreen'; // For better debugging

export default InitialInputScreen;