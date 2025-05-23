import React from 'react';
import { Briefcase, Copy, Download, ExternalLink, Eye, FileText, ArrowLeft, ArrowRight } from 'lucide-react';
import { Button, MotionButton } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@radix-ui/react-label';
import { Separator } from '@/components/ui/separator';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AppStep, AtsScore, JobData } from '@/types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, AnimateIn } from '@/components/ui/card';
import AtsScoreResultDisplay from '../joblo/AtsScoreResultDisplay';
import JobDataDisplay from '../joblo/JobDataDisplay';
import { motion } from 'framer-motion';

interface ResultsScreenProps {
  appStep: AppStep;
  scrapedJobData: JobData | null;
  jobUrl: string;
  jobInputUIMode: 'link' | 'text';
  extractedCvText: string | null;
  originalAts: AtsScore | null;
  improvedResumeMarkdown: string | null;
  improvedAts: AtsScore | null;
  docxBytesBase64: string | null;
  outputFilename: string;
  setOutputFilename: (filename: string) => void;
  handleProceedToCvPreview: () => void;
  handleProceedToAtsOriginal: () => void;
  handleProceedToGenerateResume: () => void;
  handleDownloadDocx: () => void;
  resetApp: (targetStep?: AppStep) => void;
  copyToClipboard: (text: string | undefined | null, type: string) => void;
  setAppStep: (step: AppStep) => void;
}

const ResultsDisplayCard: React.FC<{
  title: string;
  icon: React.ElementType;
  description: string;
  children: React.ReactNode;
  nextAction?: () => void;
  nextActionLabel?: string;
  prevAction?: () => void;
  prevActionLabel?: string;
}> = ({ 
  title, 
  icon: Icon, 
  description, 
  children, 
  nextAction, 
  nextActionLabel = "Next", 
  prevAction, 
  prevActionLabel = "Back" 
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -20 }}
    transition={{ duration: 0.4 }}
    className="w-full max-w-3xl mx-auto"
  >
    <Card variant="glass" className="backdrop-blur-xl border-white/10">
      <CardHeader className="relative pb-2">
        <div className="absolute -top-12 -left-12 w-24 h-24 bg-primary/5 rounded-full blur-2xl"></div>
        <div className="absolute -bottom-12 -right-12 w-24 h-24 bg-secondary/5 rounded-full blur-2xl"></div>
        <div className="flex items-center mb-1">
          <div className="mr-3 p-2 rounded-lg bg-primary/10 text-primary">
            <Icon className="h-5 w-5" />
          </div>
          <CardTitle>{title}</CardTitle>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      
      <CardContent className="pt-3">
        {children}
      </CardContent>
      
      <CardFooter className="flex justify-between pt-4 border-t border-white/10">
        {prevAction && (
          <MotionButton 
            variant="outline" 
            size="sm" 
            onClick={prevAction}
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            {prevActionLabel}
          </MotionButton>
        )}
        <div className="flex-1"></div>
        {nextAction && (
          <MotionButton 
            variant="default" 
            size="sm" 
            onClick={nextAction}
          >
            {nextActionLabel}
            <ArrowRight className="ml-1 h-4 w-4" />
          </MotionButton>
        )}
      </CardFooter>
    </Card>
  </motion.div>
);

const ResultsScreen: React.FC<ResultsScreenProps> = ({
  appStep,
  scrapedJobData,
  jobUrl,
  jobInputUIMode,
  extractedCvText,
  originalAts,
  improvedResumeMarkdown,
  improvedAts,
  docxBytesBase64,
  outputFilename,
  setOutputFilename,
  handleProceedToCvPreview,
  handleProceedToAtsOriginal,
  handleProceedToGenerateResume,
  handleDownloadDocx,
  resetApp,
  copyToClipboard,
  setAppStep
}) => {
  console.log('[ResultsScreen] Rendering with props:', { 
    appStep,
    scrapedJobData: !!scrapedJobData,
    extractedCvText: !!extractedCvText,
    originalAts: originalAts,
    improvedAts: !!improvedAts,
    improvedResumeMarkdown: !!improvedResumeMarkdown 
  });

  const isCurrentStepDataReady = React.useMemo(() => {
    let dataReady = false;
    switch (appStep) {
      case 'results_job_data':
        dataReady = !!scrapedJobData && !!originalAts;
        break;
      case 'results_cv_preview':
        dataReady = !!extractedCvText;
        break;
      case 'results_ats_original':
        dataReady = !!originalAts;
        break;
      case 'results_resume_preview':
        dataReady = !!improvedResumeMarkdown && !!improvedAts;
        break;
      default:
        dataReady = true; 
    }
    console.log(`[ResultsScreen] useMemo for isCurrentStepDataReady: appStep=${appStep}, originalAts is ${originalAts ? 'truthy' : 'falsy'}, dataReady=${dataReady}`);
    return dataReady;
  }, [appStep, scrapedJobData, extractedCvText, originalAts, improvedResumeMarkdown, improvedAts]);

  if (appStep.startsWith('results') && !isCurrentStepDataReady) {
    console.log(`[ResultsScreen] Data not ready for ${appStep}. Displaying 'Data Not Available'. originalAts value:`, originalAts);
    return (
      <div 
        className="fixed inset-0 z-[90] flex flex-col items-center justify-center p-6" 
        style={{ opacity: 1, visibility: 'visible' }}
      >
        <Card variant="glass" className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center">Data Not Available</CardTitle>
            <CardDescription className="text-center">
              The required data for this step is not available. This might be due to an error or incomplete processing.
            </CardDescription>
          </CardHeader>
          <CardFooter className="flex justify-center pt-4 pb-2">
            <MotionButton 
              variant="default" 
              onClick={() => resetApp('initial_input')}
            >
              Start Over
            </MotionButton>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div 
      className="fixed inset-0 z-[90] flex flex-col items-center justify-center p-6 overflow-y-auto" 
      style={{ opacity: appStep.startsWith('results') ? 1 : 0, visibility: appStep.startsWith('results') ? 'visible' : 'hidden' }}
    >
      <div className="w-full py-4 relative z-10">
        
        {appStep === 'results_job_data' && scrapedJobData && originalAts && (
          <ResultsDisplayCard 
            title="Job Analysis" 
            icon={Briefcase} 
            description="We've analyzed the job posting and prepared a summary of the key details."
            nextAction={handleProceedToCvPreview} 
            nextActionLabel="View Resume Text" 
            prevAction={() => resetApp('optional_kb_upload')}
            prevActionLabel="Back"
          >
            <div className="space-y-6 max-h-[70vh] overflow-y-auto pr-1.5">
              <AnimateIn>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium flex items-center">
                    <div className="h-2 w-2 bg-primary rounded-full mr-2"></div>
                    Job Intelligence Summary
                  </h3>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-7 text-xs text-foreground/50 hover:text-foreground"
                    onClick={() => copyToClipboard(JSON.stringify(scrapedJobData), 'Job data')}
                  >
                    <Copy className="h-3 w-3 mr-1.5" />
                    Copy Job Data
                  </Button>
                </div>
                <div className="glass-card bg-card/20 rounded-xl overflow-hidden">
                  <JobDataDisplay data={scrapedJobData} />
                </div>
                {jobUrl && jobInputUIMode === 'link' && (
                  <Button 
                    variant="link" 
                    size="sm" 
                    className="p-0 h-auto mt-3" 
                    asChild
                  >
                    <a href={jobUrl} target="_blank" rel="noopener noreferrer">
                      View Original Job Posting <ExternalLink className="ml-1 h-3 w-3"/>
                    </a>
                  </Button>
                )}
              </AnimateIn>
            </div>
          </ResultsDisplayCard>
        )}

         {appStep === 'results_cv_preview' && extractedCvText && (
          <ResultsDisplayCard 
            title="Resume Content" 
            icon={Eye} 
            description="Here's the text we extracted from your resume" 
            nextAction={handleProceedToAtsOriginal} 
            nextActionLabel="Run ATS Analysis" 
            prevAction={() => setAppStep('results_job_data')}
          >
            <AnimateIn>
              <div className="glass-card bg-card/20 p-4 rounded-lg text-sm">
                <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed h-[60vh] overflow-y-auto">{extractedCvText}</pre>
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                className="mt-2 text-muted-foreground hover:text-primary p-0 h-auto" 
                onClick={() => copyToClipboard(extractedCvText, 'CV Text')}
              >
                <Copy className="mr-1 h-3 w-3"/> Copy text
              </Button>
            </AnimateIn>
          </ResultsDisplayCard>
        )}

        {appStep === 'results_ats_original' && originalAts && (
          <ResultsDisplayCard 
            title="ATS Compatibility Analysis" 
            icon={FileText} 
            description="How well your current resume matches the job requirements" 
            nextAction={handleProceedToGenerateResume} 
            nextActionLabel="Generate Optimized Resume" 
            prevAction={() => setAppStep('results_cv_preview')}
          >
            <AnimateIn>
              <AtsScoreResultDisplay 
                scoreData={originalAts} 
                titlePrefix="Current Resume"
                onCopy={copyToClipboard}
              />
            </AnimateIn>
          </ResultsDisplayCard>
        )}

        {appStep === 'results_resume_preview' && improvedResumeMarkdown && improvedAts && (
          <ResultsDisplayCard 
            title="AI-Optimized Resume" 
            icon={FileText} 
            description="Your professionally tailored resume for this job application" 
            prevAction={() => setAppStep('results_ats_original')}
          >
            <div className="space-y-6 max-h-[70vh] overflow-y-auto pr-1.5">
              <AnimateIn>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium flex items-center">
                    <div className="h-2 w-2 bg-primary rounded-full mr-2"></div>
                    Generated Resume
                  </h3>
                  
                  <div className="flex space-x-2">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={() => copyToClipboard(improvedResumeMarkdown, 'Improved resume')}
                      className="h-8 text-xs"
                    >
                      <Copy className="h-3 w-3 mr-1.5" />
                      Copy Text
                    </Button>
                    
                    <Button 
                      variant="default" 
                      size="sm" 
                      onClick={handleDownloadDocx}
                      className="h-8 text-xs"
                      disabled={!docxBytesBase64}
                    >
                      <Download className="h-3 w-3 mr-1.5" />
                      Download DOCX
                    </Button>
                  </div>
                </div>
                
                <div className="glass-card bg-card/20 rounded-xl overflow-hidden p-6">
                  <div className="prose prose-sm prose-invert max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {improvedResumeMarkdown}
                    </ReactMarkdown>
                  </div>
                </div>
                
                <div className="mt-6">
                  <div className="flex items-center mb-3">
                    <div className="h-2 w-2 bg-secondary rounded-full mr-2"></div>
                    <h3 className="text-sm font-medium">Improved ATS Score</h3>
                  </div>
                  
                  <Card variant="outline" className="bg-card/20">
                    <CardContent className="pt-6">
                      <AtsScoreResultDisplay 
                        scoreData={improvedAts} 
                        titlePrefix="Optimized Resume"
                        onCopy={copyToClipboard}
                      />
                    </CardContent>
                  </Card>
                </div>
                
                <div className="mt-4">
                  <div className="flex items-center mb-3">
                    <div className="h-2 w-2 bg-accent rounded-full mr-2"></div>
                    <h3 className="text-sm font-medium">Download Options</h3>
                  </div>
                  
                  <div className="flex items-end gap-4">
                    <div className="flex-1">
                      <Label className="text-xs mb-1.5 block text-muted-foreground">
                        Filename
                      </Label>
                      <Input 
                        value={outputFilename}
                        onChange={(e) => setOutputFilename(e.target.value)}
                        className="h-9 text-sm"
                      />
                    </div>
                    <MotionButton 
                      variant="gradient" 
                      onClick={handleDownloadDocx}
                      disabled={!docxBytesBase64}
                      className="h-9"
                    >
                      <Download className="h-4 w-4 mr-1.5" />
                      Download Resume
                    </MotionButton>
                  </div>
                </div>
                
                <div className="mt-8 flex justify-center">
                  <MotionButton 
                    variant="outline"
                    onClick={() => resetApp('initial_input')} 
                    className="mx-auto"
                  >
                    Start New Optimization
                  </MotionButton>
                </div>
              </AnimateIn>
            </div>
          </ResultsDisplayCard>
        )}
      </div>
    </div>
  );
};

export default ResultsScreen; 