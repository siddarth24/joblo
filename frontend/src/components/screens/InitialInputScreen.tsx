import React, { ChangeEvent, useRef, useEffect, useState } from 'react';
import { Button, MotionButton } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@radix-ui/react-label';
import { Briefcase, FileText, LinkIcon, Type, Paperclip, XCircle, CheckCircle2, ChevronRight, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { AnimateIn } from '@/components/ui/card';
import { motion } from 'framer-motion';
import NecktieIcon from '@/components/ui/NecktieIcon';

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
  const jobUrlInputRef = useRef<HTMLInputElement>(null);
  const jobDescriptionRef = useRef<HTMLTextAreaElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  
  const [stars, setStars] = useState<{ id: number, x: number, y: number, size: number, delay: number }[]>([]);
  const [rays, setRays] = useState<{ id: number, y: number, width: number, delay: number, duration: number }[]>([]);

  useEffect(() => {
    const newStars = Array.from({ length: 120 }, (_, i) => ({
      id: i,
      x: Math.random() * 100, 
      y: Math.random() * 100, 
      size: Math.random() * 2 + 1, 
      delay: Math.random() * 5, 
    }));
    setStars(newStars);
    
    const newRays = Array.from({ length: 8 }, (_, i) => ({
      id: i,
      y: 10 + Math.random() * 80, 
      width: 40 + Math.random() * 60, 
      delay: Math.random() * 8, 
      duration: 8 + Math.random() * 12, 
    }));
    setRays(newRays);
  }, []);
  
  useEffect(() => {
    const button = buttonRef.current;
    const glow = glowRef.current;
    
    if (!button || !glow) return;
    
    const handleMouseMove = (e: MouseEvent) => {
      const rect = button.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      
      glow.style.setProperty('--x', `${x}%`);
      glow.style.setProperty('--y', `${y}%`);
    };
    
    button.addEventListener('mousemove', handleMouseMove);
    
    return () => {
      button.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 relative overflow-hidden">
      <div className="cosmic-background">
        <motion.div 
          className="cosmic-blob"
          style={{ 
            background: 'radial-gradient(circle at center, rgba(var(--neon-blue), 0.7), rgba(var(--primary), 0.4))',
            width: '500px',
            height: '500px',
            left: '10%',
            top: '20%',
          }}
          animate={{ 
            x: [0, 30, 0],
            y: [0, -30, 0],
            scale: [1, 1.1, 1]
          }}
          transition={{ 
            repeat: Infinity,
            duration: 15,
            ease: "easeInOut"
          }}
        />
        
        <motion.div 
          className="cosmic-blob"
          style={{ 
            background: 'radial-gradient(circle at center, rgba(var(--neon-purple), 0.7), rgba(var(--secondary), 0.4))',
            width: '400px',
            height: '400px',
            right: '10%',
            bottom: '15%',
          }}
          animate={{ 
            x: [0, -40, 0],
            y: [0, 40, 0],
            scale: [1, 1.2, 1]
          }}
          transition={{ 
            repeat: Infinity,
            duration: 18,
            ease: "easeInOut",
            delay: 2
          }}
        />
        
        <motion.div 
          className="cosmic-blob"
          style={{ 
            background: 'radial-gradient(circle at center, rgba(var(--neon-teal), 0.7), rgba(var(--accent), 0.4))',
            width: '450px',
            height: '450px',
            right: '30%',
            top: '5%',
          }}
          animate={{ 
            x: [0, 20, 0],
            y: [0, 20, 0],
            scale: [1, 1.15, 1]
          }}
          transition={{ 
            repeat: Infinity,
            duration: 20,
            ease: "easeInOut",
            delay: 1
          }}
        />
        
        <div className="cosmic-grid" />
        
        {stars.map(star => (
          <motion.div
            key={star.id}
            className="cosmic-star"
            style={{
              left: `${star.x}%`,
              top: `${star.y}%`,
              width: `${star.size}px`,
              height: `${star.size}px`,
            }}
            animate={{ 
              opacity: [0.2, 0.8, 0.2],
              scale: [0.8, 1.2, 0.8]
            }}
            transition={{ 
              repeat: Infinity, 
              duration: 3 + Math.random() * 3,
              delay: star.delay,
              ease: "easeInOut"
            }}
          />
        ))}
        
        {rays.map(ray => (
          <motion.div
            key={ray.id}
            className="cosmic-ray"
            style={{
              top: `${ray.y}%`,
              width: `${ray.width}%`,
              left: 0,
              opacity: 0
            }}
            animate={{ 
              opacity: [0, 0.7, 0],
              x: ["0%", "100%"]
            }}
            transition={{ 
              repeat: Infinity, 
              duration: ray.duration,
              delay: ray.delay,
              ease: "easeInOut"
            }}
          />
        ))}
        
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-0 h-0">
          {[...Array(5)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute rounded-full"
              style={{
                width: 3 + i,
                height: 3 + i,
                backgroundColor: i % 2 === 0 ? 'rgba(var(--primary), 0.8)' : 'rgba(var(--secondary), 0.8)',
                boxShadow: i % 2 === 0 
                  ? '0 0 8px 2px rgba(var(--primary), 0.4)' 
                  : '0 0 8px 2px rgba(var(--secondary), 0.4)',
                transformOrigin: 'center',
                x: 100 + i * 30,
                y: 0
              }}
              animate={{
                rotate: [0, 360]
              }}
              transition={{
                duration: 10 + i * 3,
                ease: "linear",
                repeat: Infinity,
                delay: i * 0.6
              }}
            />
          ))}
        </div>
      </div>
      
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-md relative z-10"
      >
        <div className="flex flex-col items-center mb-8">
          <div className="relative w-20 h-20 mb-6 flex items-center justify-center">
            <div className="absolute inset-0 bg-primary/30 rounded-full blur-xl"></div>
            <motion.div 
              animate={{ rotate: 360 }}
              transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
              className="absolute inset-2 rounded-full"
            />
            <motion.div
              animate={{ rotate: -360 }}
              transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
              className="absolute inset-4 rounded-full"
            />
            <motion.div
              initial={{ scale: 0.8 }}
              animate={{ scale: [0.8, 1, 0.8] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
              className="relative"
            >
              <NecktieIcon 
                width={48}
                height={48}
                animate={true}
                glowEffect={true}
              />
            </motion.div>
          </div>
          
          <motion.h1 
            className="text-4xl font-semibold mb-2 relative"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.7 }}
          >
            <span className="mr-1">Joblo</span>
            <span className="text-gradient ai-gradient bg-clip-text text-transparent">AI</span>
          </motion.h1>
          
          <motion.p 
            className="text-muted-foreground text-center max-w-xs"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.7 }}
          >
            Create a tailored resume that gets past ATS systems and impresses recruiters
          </motion.p>
        </div>
        
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.7 }}
          className="glass-card-pro rounded-xl p-8 shadow-lg relative overflow-hidden hover-card-parallax"
        >
          <div className="absolute inset-0 dot-pattern opacity-30"></div>
          
          <div className="corner-accent absolute top-0 right-0 w-24 h-24"></div>
          <div className="corner-accent absolute bottom-0 left-0 w-24 h-24"></div>
          
          <AnimateIn delay={0.1} className="space-y-7 relative z-10">
            <div className="mb-6 relative">
              <div className="mb-2">
                <Label className="text-sm text-foreground/90 flex items-center font-medium mb-2">
                  <Briefcase className="h-3.5 w-3.5 mr-1.5 opacity-80" />
                  Job Input Method
                </Label>
              </div>
              <div className="custom-toggle-container">
                <div 
                  className={`custom-toggle-background ${jobInputUIMode === 'link' ? 'toggle-left' : 'toggle-right'}`}
                aria-hidden="true" 
              />
                
                <button
                  type="button"
                onClick={() => setJobInputUIMode('link')} 
                  className={`custom-toggle-option ${jobInputUIMode === 'link' ? 'active' : 'inactive'}`}
                >
                  <span className="toggle-icon-container">
                    <LinkIcon className="h-4 w-4" />
                  </span>
                  <span className="toggle-text relative">
                    URL
                    {jobInputUIMode === 'link' && (
                      <motion.span 
                        className="active-indicator" 
                        layoutId="activeIndicator"
                        initial={{ scale: 0.8, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ type: "spring", stiffness: 500, damping: 30 }}
                      />
                    )}
                  </span>
                </button>
                
                <button
                  type="button"
                onClick={() => setJobInputUIMode('text')} 
                  className={`custom-toggle-option ${jobInputUIMode === 'text' ? 'active' : 'inactive'}`}
                >
                  <span className="toggle-icon-container">
                    <Type className="h-4 w-4" />
                  </span>
                  <span className="toggle-text relative">
                    Text
                    {jobInputUIMode === 'text' && (
                      <motion.span 
                        className="active-indicator" 
                        layoutId="activeIndicator"
                        initial={{ scale: 0.8, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ type: "spring", stiffness: 500, damping: 30 }}
                      />
                    )}
                  </span>
                </button>
              </div>
            </div>
            
            {jobInputUIMode === 'link' ? (
              <AnimateIn key="link-input" className="space-y-2">
                <Label className="text-sm text-foreground/90 flex items-center font-medium">
                  <Briefcase className="h-3.5 w-3.5 mr-1.5 opacity-80" />
                  Job URL
                </Label>
                <div className="relative group">
                  <Input 
                    ref={jobUrlInputRef}
                    type="url" 
                    placeholder="https://example.com/job" 
                    value={jobUrl} 
                    onChange={(e) => setJobUrl(e.target.value)}
                    className="pl-9 h-12 bg-black/20 border-white/10 rounded-lg focus-trap shadow-inner transition-all"
                  />
                  <LinkIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-foreground/60 group-focus-within:text-primary" />
                  
                  <motion.div 
                    className="absolute bottom-0 left-0 h-[2px] bg-gradient-to-r from-primary to-secondary rounded-full"
                    initial={{ width: "0%" }}
                    animate={{ width: jobUrl.length ? "100%" : "0%" }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
              </AnimateIn>
            ) : (
              <AnimateIn key="text-input" className="space-y-2">
                <Label className="text-sm text-foreground/90 flex items-center font-medium">
                  <Briefcase className="h-3.5 w-3.5 mr-1.5 opacity-80" />
                  Job Description
                </Label>
                <div className="relative group">
                <Textarea 
                  ref={jobDescriptionRef}
                  placeholder="Paste job description..." 
                  value={jobDescription} 
                  onChange={(e) => setJobDescription(e.target.value)}
                    className="min-h-[140px] resize-none bg-black/20 border-white/10 rounded-lg focus-trap shadow-inner transition-all"
                  />
                  
                  <motion.div 
                    className="absolute bottom-0 left-0 h-[2px] bg-gradient-to-r from-primary to-secondary rounded-full"
                    initial={{ width: "0%" }}
                    animate={{ width: jobDescription.length ? "100%" : "0%" }}
                    transition={{ duration: 0.3 }}
                />
                </div>
              </AnimateIn>
            )}
            
            <AnimateIn delay={0.2} className="space-y-2">
              <Label className="text-sm text-foreground/90 flex items-center font-medium">
                <FileText className="h-3.5 w-3.5 mr-1.5 opacity-80" />
                Resume
              </Label>
              <div className="relative flex items-center">
                <Button 
                  variant={resumeFile ? "outline" : "outline"} 
                  onClick={handleAttachResumeClick} 
                  className={cn(
                    "w-full justify-start text-sm h-12 pl-4 border-white/10 bg-black/20 hover:bg-black/30 transition-all duration-300",
                    resumeFile && "border-primary/40 bg-primary/10 hover:bg-primary/15 pr-12"
                  )}
                >
                  {resumeFile ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 mr-2 text-primary" />
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
                    className="absolute right-1 h-10 w-10 text-foreground/40 hover:text-destructive hover:bg-destructive/10 rounded-md p-0 transition-all duration-300"
                  >
                    <XCircle className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </AnimateIn>
            
            <AnimateIn delay={0.3}>
              <motion.div
                whileHover={{ scale: canSubmitInitial ? 1.03 : 1 }}
                whileTap={{ scale: canSubmitInitial ? 0.97 : 1 }}
                transition={{ duration: 0.2, type: "spring", stiffness: 400 }}
              >
              <MotionButton 
                  ref={buttonRef}
                onClick={proceedToKbUpload} 
                disabled={!canSubmitInitial || appStep === 'loading'} 
                variant={canSubmitInitial ? "gradient" : "grayscale"}
                  className={`w-full h-12 mt-4 rounded-lg ${canSubmitInitial ? 'enhanced-gradient-button' : ''} relative overflow-hidden group font-semibold`}
                  animate={false}
              >
                  <span className="relative z-10 flex items-center justify-center gap-1">
                    <span>Continue</span>
                    <ChevronRight className="h-5 w-5 transition-transform duration-300 group-hover:translate-x-0.5" />
                    {canSubmitInitial && 
                      <Sparkles className="ml-0.5 h-[18px] w-[18px] transition-opacity duration-300 opacity-0 group-hover:opacity-100" />
                    }
                  </span>
                  {canSubmitInitial && <div ref={glowRef} className="absolute inset-0 animated-glow"></div>}
              </MotionButton>
              </motion.div>
              
              <input 
                type="file" 
                ref={hiddenResumeInputRef} 
                onChange={handleResumeFileChange}
                accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document" 
                className="hidden" 
              />
            </AnimateIn>
          </AnimateIn>
        </motion.div>
      </motion.div>
    </div>
  );
});

InitialInputScreen.displayName = 'InitialInputScreen'; // For better debugging

export default InitialInputScreen;