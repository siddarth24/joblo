import React from 'react';
import { Briefcase, Copy, Download, ExternalLink, Eye, LinkIcon, Send, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@radix-ui/react-label';
import { Separator } from '@/components/ui/separator';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AppStep, AtsScore, JobData } from '@/types';
import ResultsDisplayCard from '../joblo/ResultsDisplayCard';
import AtsScoreResultDisplay from '../joblo/AtsScoreResultDisplay';
import JobDataDisplay from '../joblo/JobDataDisplay';

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
  return (
    <div 
      className="fixed inset-0 z-[90] flex flex-col items-center justify-center bg-black/90 backdrop-blur-md p-4 pt-16 pb-16 overflow-y-auto transition-opacity duration-500 ease-in-out" 
      style={{ opacity: appStep.startsWith('results') ? 1 : 0, visibility: appStep.startsWith('results') ? 'visible' : 'hidden' }}
    >
      <div className="aurora-bg opacity-30">
        <div className="aurora-gradient aurora-g1"></div>
        <div className="aurora-gradient aurora-g2"></div>
      </div>
      <div className="w-full py-4 relative z-10">
        
        {/* Step: Show Job Data */}
        {appStep === 'results_job_data' && scrapedJobData && (
          <ResultsDisplayCard 
            title="Job Analysis" 
            icon={Briefcase} 
            description="Key information extracted from job posting" 
            nextAction={handleProceedToCvPreview} 
            nextActionLabel="View Resume" 
            prevAction={() => resetApp('optional_kb_upload')}
            prevActionLabel="Back"
          >
            <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1.5 modern-scrollbar">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center">
                  <div className="h-2 w-2 bg-cyan-400 rounded-full mr-2"></div>
                  <h3 className="text-sm font-medium text-white/90">Job Intelligence Summary</h3>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-7 text-xs text-white/40 hover:text-white hover:bg-white/10"
                  onClick={() => copyToClipboard(JSON.stringify(scrapedJobData), 'Job data')}
                >
                  <Copy className="h-3 w-3 mr-1.5" />
                  Copy Data
                </Button>
              </div>
              
              <div className="frost-glass rounded-xl overflow-hidden border border-white/10">
                <JobDataDisplay data={scrapedJobData} />
              </div>
              
              {jobUrl && jobInputUIMode === 'link' && (
                <Button 
                  variant="link" 
                  size="sm" 
                  className="p-0 h-auto mt-3 text-cyan-500 hover:text-cyan-400 transition-colors" 
                  asChild
                >
                  <a href={jobUrl} target="_blank" rel="noopener noreferrer">
                    View Original Job Posting <ExternalLink className="ml-1 h-3 w-3"/>
                  </a>
                </Button>
              )}
            </div>
          </ResultsDisplayCard>
        )}

        {/* Step: Show CV Preview */}
         {appStep === 'results_cv_preview' && extractedCvText && (
          <ResultsDisplayCard 
            title="Current Resume" 
            icon={Eye} 
            description="Text extracted from your resume" 
            nextAction={handleProceedToAtsOriginal} 
            nextActionLabel="Run ATS Analysis" 
            prevAction={() => setAppStep('results_job_data')}
          >
            <pre className="p-3 bg-neutral-900/40 border border-neutral-800/60 rounded-md text-xs text-neutral-300 overflow-x-auto max-h-[60vh]">{extractedCvText}</pre>
            <Button 
              variant="ghost" 
              size="sm" 
              className="mt-2 text-neutral-500 hover:text-cyan-500 p-0 h-auto" 
              onClick={() => copyToClipboard(extractedCvText, 'CV Text')}
            >
              <Copy className="mr-1 h-3 w-3"/> Copy text
            </Button>
          </ResultsDisplayCard>
        )}

        {/* Step: Show Original ATS */}
        {appStep === 'results_ats_original' && originalAts && (
          <ResultsDisplayCard 
            title="Initial ATS Analysis" 
            icon={FileText} 
            description="Current resume compatibility assessment" 
            nextAction={handleProceedToGenerateResume} 
            nextActionLabel="Generate Optimized Resume" 
            prevAction={() => setAppStep('results_cv_preview')}
          >
            <AtsScoreResultDisplay 
              scoreData={originalAts} 
              titlePrefix="Current" 
              onCopy={copyToClipboard}
            />
          </ResultsDisplayCard>
        )}

        {/* Step: Show Final Results */}
        {appStep === 'results_resume_preview' && improvedResumeMarkdown && improvedAts && (
          <ResultsDisplayCard 
            title="Optimized Resume" 
            icon={FileText} 
            description="AI-enhanced resume with improved ATS compatibility" 
            prevAction={() => setAppStep('results_ats_original')}
          >
            <div className="space-y-6">
              <div>
                <h3 className="text-base font-medium text-white mb-2">Enhanced Resume:</h3>
                <div className="prose prose-sm prose-invert max-w-none p-3 bg-neutral-900/40 border border-neutral-800/60 rounded-md max-h-96 overflow-y-auto prose-headings:text-cyan-500 prose-strong:text-white prose-a:text-amber-400 hover:prose-a:text-amber-300">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{improvedResumeMarkdown}</ReactMarkdown>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="mt-2 text-neutral-500 hover:text-cyan-500 p-0 h-auto" 
                  onClick={() => copyToClipboard(improvedResumeMarkdown, 'Resume Markdown')}
                >
                  <Copy className="mr-1 h-3 w-3"/> Copy markdown
                </Button>
              </div>
              
              <Separator className="bg-neutral-800/60"/>
              
              <div>
                <h3 className="text-base font-medium text-white mb-2">ATS Compatibility Analysis:</h3>
                <AtsScoreResultDisplay 
                  scoreData={improvedAts} 
                  titlePrefix="Optimized" 
                  comparisonScore={originalAts?.score}
                  onCopy={copyToClipboard}
                />
              </div>
              
              <Separator className="bg-neutral-800/60"/>
              
              <div>
                <Label htmlFor="finalOutputFilename" className="text-sm text-neutral-400">Output Filename:</Label>
                <Input 
                  id="finalOutputFilename" 
                  value={outputFilename} 
                  onChange={(e) => setOutputFilename(e.target.value)} 
                  className="mt-1 bg-neutral-900/60 border-neutral-800 text-neutral-200 focus:border-cyan-700 focus:ring-0" 
                />
              </div>
              
              {docxBytesBase64 && (
                <Button 
                  onClick={handleDownloadDocx} 
                  className="w-full py-5 bg-emerald-600 hover:bg-emerald-500 text-white transition-colors"
                >
                  <Download className="mr-2 h-4 w-4" /> Download DOCX
                </Button>
              )}
              
              <Button 
                variant="outline" 
                onClick={() => resetApp()} 
                className="w-full border-neutral-800 text-neutral-300 bg-neutral-900/60 hover:bg-neutral-800 hover:text-white transition-colors"
              >
                Start New Analysis
              </Button>
            </div>
          </ResultsDisplayCard>
        )}
      </div>
    </div>
  );
};

export default ResultsScreen; 