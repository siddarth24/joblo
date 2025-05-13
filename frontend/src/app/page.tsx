"use client";

import React, { useState, ChangeEvent, useCallback, useEffect, useRef } from 'react';
import { ThemeProvider, useTheme } from 'next-themes';
import { Toaster, toast } from 'sonner';

// Types
import { AppStep, JobInputUIMode, AtsScore, JobData, ProcessingResult, ApiResponse } from '@/types';

// Components
import Header from '@/components/joblo/Header';
import InitialInputScreen from '@/components/screens/InitialInputScreen';
import KnowledgeBaseUploadScreen from '@/components/screens/KnowledgeBaseUploadScreen';
import LoadingScreen from '@/components/screens/LoadingScreen';
import ResultsScreen from '@/components/screens/ResultsScreen';
import ErrorScreen from '@/components/screens/ErrorScreen';

// Services
import { 
  processJobApplication,
  checkApiHealth
} from '@/services/api';

// --- Main Application Component ---
const App: React.FC = () => {
  const { theme, setTheme } = useTheme();
  const [appStep, setAppStep] = useState<AppStep>('initial_input');
  const [jobInputUIMode, setJobInputUIMode] = useState<JobInputUIMode>('link');

  const [jobUrl, setJobUrl] = useState<string>('');
  const [jobDescription, setJobDescription] = useState<string>('');

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [knowledgeBaseFiles, setKnowledgeBaseFiles] = useState<File[]>([]);
  const hiddenResumeInputRef = useRef<HTMLInputElement | null>(null);
  const hiddenKbInputRef = useRef<HTMLInputElement>(null);

  const [isLoadingMessage, setIsLoadingMessage] = useState<string>('Initiating Analysis Protocol...');
  const [scrapedJobData, setScrapedJobData] = useState<JobData | null>(null);
  const [extractedCvText, setExtractedCvText] = useState<string | null>(null);
  const [originalAts, setOriginalAts] = useState<AtsScore | null>(null);
  const [improvedResumeMarkdown, setImprovedResumeMarkdown] = useState<string | null>(null);
  const [improvedAts, setImprovedAts] = useState<AtsScore | null>(null);
  const [docxBytesBase64, setDocxBytesBase64] = useState<string | null>(null);
  const [outputFilename, setOutputFilename] = useState<string>('Improved_Resume.docx');

  useEffect(() => {
    if (theme !== 'dark') {
      setTheme('dark');
    }
  }, [theme, setTheme]);

  // Handlers to be passed as props, memoized with useCallback
  const memoizedSetJobInputUIMode = useCallback((mode: JobInputUIMode) => setJobInputUIMode(mode), []);
  const memoizedSetJobUrl = useCallback((url: string) => setJobUrl(url), []);
  const memoizedSetJobDescription = useCallback((desc: string) => setJobDescription(desc), []);

  const handleAttachResumeClick = useCallback(() => hiddenResumeInputRef.current?.click(), []);
  const handleAttachKbClick = useCallback(() => hiddenKbInputRef.current?.click(), []);

  const handleResumeFileChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setResumeFile(event.target.files[0]);
      toast.success(`Resume selected: ${event.target.files[0].name}`);
    }
    if (event.target) event.target.value = ""; // Clear input for re-selection
  }, []);

  const handleKbFilesChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      const filesArray = Array.from(event.target.files);
      setKnowledgeBaseFiles(prev => [...prev, ...filesArray]);
      toast.success(`${filesArray.length} knowledge file(s) added.`);
    }
    if (event.target) event.target.value = ""; // Clear input
  }, []);

  const removeResumeFile = useCallback(() => {
    setResumeFile(null);
    toast.info("Resume file removed.");
  }, []);

  const removeKbFile = useCallback((fileNameToRemove: string) => {
    setKnowledgeBaseFiles(prev => prev.filter(file => file.name !== fileNameToRemove));
    toast.info(`Knowledge file "${fileNameToRemove}" removed.`);
  }, []);

  const canSubmitInitial = React.useMemo(() => {
    const jobInputValid = jobInputUIMode === 'link' 
      ? (jobUrl.trim().startsWith('http://') || jobUrl.trim().startsWith('https://')) 
      : jobDescription.trim().length > 20;
    return jobInputValid && resumeFile !== null;
  }, [jobInputUIMode, jobUrl, jobDescription, resumeFile]);

  const proceedToKbUpload = useCallback(() => {
     if (!canSubmitInitial) {
      if (!resumeFile) toast.error("Please attach your resume.");
      if (jobInputUIMode === 'link' && !(jobUrl.trim().startsWith('http://') || jobUrl.trim().startsWith('https://'))) 
        toast.error("Please enter a valid job URL.");
      if (jobInputUIMode === 'text' && jobDescription.trim().length <= 20) 
        toast.error("Job description seems too short.");
      return;
    }
    setAppStep('optional_kb_upload');
  }, [canSubmitInitial, resumeFile, jobInputUIMode, jobUrl, jobDescription]);

  const startFullProcessing = useCallback(async (skipKb: boolean = false) => {
    setAppStep('loading');
    setIsLoadingMessage('Initializing Core Analysis...');
    setScrapedJobData(null); 
    setExtractedCvText(null); 
    setOriginalAts(null);
    setImprovedResumeMarkdown(null); 
    setImprovedAts(null); 
    setDocxBytesBase64(null);

    const formData = new FormData();
    if (jobInputUIMode === 'link') formData.append('jobUrl', jobUrl);
    else formData.append('jobDescription', jobDescription);
    if (resumeFile) formData.append('resumeFile', resumeFile);
    if (!skipKb) knowledgeBaseFiles.forEach(file => formData.append('kbFiles', file));
    
    try {
      setIsLoadingMessage('Deconstructing Job Posting & Parsing Resume...');
      
      const isHealthy = await checkApiHealth();
      console.log('API health check:', isHealthy); // Keep for basic health check visibility
      
      if (!isHealthy) {
        throw new Error("API service is currently unavailable. Please try again later.");
      }

      console.log('Sending process job application request');
      const response = await processJobApplication(formData);
      console.log('Process job application response:', response); // Keep for initial data visibility
      
      if (!response.success || !response.data) {
        toast.error(response.error || "Failed to process application. Please check inputs and API logs.");
        setAppStep('error');
        return;
      }
      
      const result = response.data as ProcessingResult;
      console.log('Setting scraped job data:', result.jobData);
      console.log('Setting extracted CV text (truncated):', 
                result.extractedCvText ? result.extractedCvText.substring(0, 100) + '...' : 'none');
      
      setScrapedJobData(result.jobData);
      setExtractedCvText(result.extractedCvText);
      // The initial response should now contain the original ATS score directly from the backend
      if (result.originalAts) {
        console.log('Setting original ATS from initial processing:', result.originalAts);
        setOriginalAts(result.originalAts);
      } else {
        // This case should ideally not happen if backend is structured correctly for initial ATS
        console.warn('Original ATS score not found in initial process-job-application response.');
        // Optionally, trigger an error or a specific state if original ATS is critical here
      }

      if (result.outputFilename) {
        setOutputFilename(result.outputFilename);
      } else {
        setOutputFilename(`${result.jobData?.["Job Title"] || 'Job'}_${result.jobData?.["Company"] || 'Company'}_Resume.docx`);
      }
      
      setAppStep('results_job_data'); 
    } catch (error: any) { 
      console.error('Process job application error:', error);
      toast.error((error as Error).message || "System matrix destabilized during initial phase."); 
      setAppStep('error'); 
    }
  }, [jobInputUIMode, jobUrl, jobDescription, resumeFile, knowledgeBaseFiles]);

  const handleProceedToCvPreview = useCallback(() => setAppStep('results_cv_preview'), []);

  const handleProceedToAtsOriginal = useCallback(async () => {
    if (!scrapedJobData || !extractedCvText) {
        toast.error("Missing job data or CV text for ATS analysis.");
        setAppStep('error');
        return;
    }
    setAppStep('loading'); 
    setIsLoadingMessage('Calculating Pre-Enhancement ATS Signature...');
    console.log('[CLIENT handleProceedToAtsOriginal] State before fetch:', { 
      scrapedJobData: !!scrapedJobData,
      extractedCvText: !!extractedCvText,
      originalAts: originalAts // Log current originalAts state
    });
    try {
      const formData = new FormData();
      formData.append('jobData', JSON.stringify(scrapedJobData));
      formData.append('cvText', extractedCvText || '');
      
      console.log('[CLIENT handleProceedToAtsOriginal] Sending ATS analysis request with jobData keys:', Object.keys(scrapedJobData || {}));
      console.log('[CLIENT handleProceedToAtsOriginal] Sending CV text (length):', (extractedCvText || '').length);
      
      const response = await fetch('/api/analyze-ats', {
        method: 'POST',
        body: formData,
      });
      
      const resultText = await response.text(); // Get text first to avoid issues with response.json() being called twice
      console.log('[CLIENT handleProceedToAtsOriginal] Raw response text:', resultText);
      const result = JSON.parse(resultText);
      console.log('[CLIENT handleProceedToAtsOriginal] Parsed fetch result:', result);
      
      if (!result.success || !result.data?.atsScore || typeof result.data.atsScore !== 'object') {
        console.error('[CLIENT handleProceedToAtsOriginal] ATS score data is invalid or missing. Result:', result);
        toast.error(result.error || "Failed to analyze ATS score. Data missing or invalid from response.");
        setAppStep('error');
        return;
      }
      
      console.log('[CLIENT handleProceedToAtsOriginal] Setting originalAts with:', result.data.atsScore);
      setOriginalAts(result.data.atsScore);
      setAppStep('results_ats_original');
      console.log('[CLIENT handleProceedToAtsOriginal] State update calls made.');
    } catch (error: any) { 
      console.error('[CLIENT handleProceedToAtsOriginal] ATS analysis error:', error, error.stack);
      toast.error((error as Error).message || "ATS analysis failed."); 
      setAppStep('error'); 
    }
  }, [scrapedJobData, extractedCvText, originalAts]); // Added originalAts to dependency array as it's logged, though not strictly necessary for the logic itself
  
  const handleProceedToGenerateResume = useCallback(async () => {
    if (!scrapedJobData || !extractedCvText || !originalAts) {
        toast.error("Missing required data (job, CV, or original ATS) to generate resume.");
        setAppStep('error');
        return;
    }
    setAppStep('loading'); 
    setIsLoadingMessage('Engaging AI Core for Resume Synthesis...');
    try {
      const formData = new FormData();
      formData.append('jobData', JSON.stringify(scrapedJobData));
      formData.append('cvText', extractedCvText || '');
      formData.append('atsScore', JSON.stringify(originalAts)); // Send original ATS for context
      
      knowledgeBaseFiles.forEach(file => formData.append('kbFiles', file));
      
      const response = await fetch('/api/generate-resume', { // This calls the Next.js API route
        method: 'POST',
        body: formData,
      });
      
      const result = await response.json();
      console.log('Generate resume response:', result); // For debugging

      if (!result.success || !result.data) {
        toast.error(result.error || "Failed to generate improved resume. Data missing from response.");
        setAppStep('error');
        return;
      }
      
      setImprovedResumeMarkdown(result.data.improvedResumeMarkdown);
      setImprovedAts(result.data.improvedAts); 
      setDocxBytesBase64(result.data.docxBytesBase64);
      if(result.data.outputFilename) setOutputFilename(result.data.outputFilename);
      setAppStep('results_resume_preview');
    } catch (error: any) { 
      console.error('Resume generation error:', error);
      toast.error((error as Error).message || "AI synthesis encountered an anomaly."); 
      setAppStep('error'); 
    }
  }, [scrapedJobData, extractedCvText, originalAts, knowledgeBaseFiles]);

  const handleDownloadDocx = useCallback(() => { 
    if (!docxBytesBase64) { 
      toast.error("DOCX data stream not available."); 
      return; 
    }
    
    // Check if we're dealing with mock data
    if (docxBytesBase64.includes("(mocked)")) {
      toast.info("Mock data detected. In production, this would download a real DOCX file.");
      return;
    }
    
    try {
      const byteCharacters = atob(docxBytesBase64);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) byteNumbers[i] = byteCharacters.charCodeAt(i);
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; 
      link.download = outputFilename;
      document.body.appendChild(link); 
      link.click(); 
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success(`Download initiated: ${link.download}`);
    } catch (e) { 
      console.error("Download error:", e); 
      toast.error("Failed to decode DOCX data.");
    }
  }, [docxBytesBase64, outputFilename]);
  
  const resetApp = useCallback((targetStep: AppStep = 'initial_input') => {
    setJobUrl(''); 
    setJobDescription(''); 
    setResumeFile(null); 
    setKnowledgeBaseFiles([]);
    setAppStep(targetStep);
  }, []);

  const copyToClipboard = useCallback((text: string | undefined | null, type: string) => {
    if (!text) {
      toast.error(`No ${type} text available to copy.`);
      return;
    }
    navigator.clipboard.writeText(text)
      .then(() => toast.success(`${type} copied to clipboard!`))
      .catch(() => toast.error(`Failed to copy ${type}.`));
  }, []);

  const memoizedSetOutputFilename = useCallback((name: string) => setOutputFilename(name), []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#050a14] to-black text-white flex flex-col font-sans relative overflow-hidden">
      {/* Render global background only when no overlay is fully visible */}
      {appStep === 'initial_input' && (
        <div className="aurora-bg">
          <div className="aurora-gradient aurora-g1"></div>
          <div className="aurora-gradient aurora-g2"></div>
        </div>
      )}

      <Header />
      
      <div className="flex-grow flex flex-col relative z-10">
        {appStep === 'initial_input' && (
          <InitialInputScreen
            jobInputUIMode={jobInputUIMode}
            setJobInputUIMode={memoizedSetJobInputUIMode}
            jobUrl={jobUrl}
            setJobUrl={memoizedSetJobUrl}
            jobDescription={jobDescription}
            setJobDescription={memoizedSetJobDescription}
            resumeFile={resumeFile}
            handleAttachResumeClick={handleAttachResumeClick}
            removeResumeFile={removeResumeFile}
            canSubmitInitial={canSubmitInitial}
            proceedToKbUpload={proceedToKbUpload}
            appStep={appStep}
            hiddenResumeInputRef={hiddenResumeInputRef}
            handleResumeFileChange={handleResumeFileChange}
          />
        )}
      </div>

      {/* These components are mounted but visibility controlled by their props */}
      <KnowledgeBaseUploadScreen 
        handleAttachKbClick={handleAttachKbClick}
        knowledgeBaseFiles={knowledgeBaseFiles}
        removeKbFile={removeKbFile}
        startFullProcessing={startFullProcessing}
        isVisible={appStep === 'optional_kb_upload'}
      />

      <input 
        type="file" 
        ref={hiddenKbInputRef} 
        onChange={handleKbFilesChange} 
        className="hidden" 
        accept=".pdf,.doc,.docx,.txt" 
        multiple 
      />

      <LoadingScreen 
        isLoading={appStep === 'loading'} 
        loadingMessage={isLoadingMessage} 
      />
      
      <ResultsScreen 
        appStep={appStep}
        scrapedJobData={scrapedJobData}
        jobUrl={jobUrl}
        jobInputUIMode={jobInputUIMode}
        extractedCvText={extractedCvText}
        originalAts={originalAts}
        improvedResumeMarkdown={improvedResumeMarkdown}
        improvedAts={improvedAts}
        docxBytesBase64={docxBytesBase64}
        outputFilename={outputFilename}
        setOutputFilename={memoizedSetOutputFilename}
        handleProceedToCvPreview={handleProceedToCvPreview}
        handleProceedToAtsOriginal={handleProceedToAtsOriginal}
        handleProceedToGenerateResume={handleProceedToGenerateResume}
        handleDownloadDocx={handleDownloadDocx}
        resetApp={resetApp}
        copyToClipboard={copyToClipboard}
        setAppStep={setAppStep}
      />
      
      <ErrorScreen 
        isError={appStep === 'error'} 
        resetApp={resetApp} 
      />
      
      <Toaster theme="dark" position="bottom-right" closeButton richColors />
    </div>
  );
};

export default function JobloAppPage() {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} forcedTheme="dark">
      <App />
    </ThemeProvider>
  );
} 