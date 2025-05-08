"use client";

import React, { useState, ChangeEvent, useCallback, useEffect, useRef } from 'react';
import { ThemeProvider, useTheme } from 'next-themes';
import { Toaster, toast } from 'sonner';

// API client
import { api } from '../services/api';

// Types
import { AppStep, JobInputUIMode, AtsScore, JobData } from '@/types';
import { JobApplicationPayload } from '../types/api';

// Components
import Header from '@/components/joblo/Header';
import InitialInputScreen from '@/components/screens/InitialInputScreen';
import KnowledgeBaseUploadScreen from '@/components/screens/KnowledgeBaseUploadScreen';
import LoadingScreen from '@/components/screens/LoadingScreen';
import ResultsScreen from '@/components/screens/ResultsScreen';
import ErrorScreen from '@/components/screens/ErrorScreen';

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

  // Backend Health Check on Mount
  useEffect(() => {
    const checkBackendStatus = async () => {
      toast.promise(api.healthCheck(), {
        loading: 'Connecting to backend...',
        success: (response) => {
          if (response.success && response.data?.status === 'ok') {
            return 'Backend connection established!';
          }
          return `Backend status: ${response.error || 'Unknown error'}`;
        },
        error: (err) => `Backend connection failed: ${err.message || 'Unknown error'}`,
      });
    };
    checkBackendStatus();
  }, []);

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

  // --- Refined Processing Flow Callbacks ---
  const startFullProcessing = useCallback(async (skipKb: boolean = false) => {
    if (!resumeFile) {
      toast.error("No resume file selected. Please select a resume to proceed.");
      setAppStep('initial_input'); // Go back if critical info is missing
      return;
    }

    setAppStep('loading');
    setIsLoadingMessage('Initiating Full Analysis Protocol with Backend...');
    
    // Clear previous results
    setScrapedJobData(null); 
    setExtractedCvText(null); 
    setOriginalAts(null);
    setImprovedResumeMarkdown(null); 
    setImprovedAts(null); 
    setDocxBytesBase64(null);

    // Prepare payload for the API
    const payload: JobApplicationPayload = { resumeFile };
    if (jobInputUIMode === 'link' && jobUrl) {
      payload.jobUrl = jobUrl;
    } else if (jobInputUIMode === 'text' && jobDescription) {
      payload.jobDescription = jobDescription;
    } else if (jobInputUIMode === 'link' && !jobUrl) {
        toast.error("Job URL is selected but no URL is provided.");
        setAppStep('initial_input');
        return;
    } else if (jobInputUIMode === 'text' && !jobDescription) {
        toast.error("Job Description is selected but no description is provided.");
        setAppStep('initial_input');
        return;
    }


    if (!skipKb && knowledgeBaseFiles.length > 0) {
      payload.kbFiles = knowledgeBaseFiles;
    }
    
    try {
      setIsLoadingMessage('Transmitting data to backend for analysis...');
      const response = await api.processJobApplication(payload);

      if (response.success && response.data) {
        toast.success(response.message || 'Processing successful!');
        
        // Update state with data from backend
        setScrapedJobData(response.data.scrapedJobData);
        setExtractedCvText(response.data.extractedCvText);
        setOriginalAts(response.data.originalAts);
        setImprovedResumeMarkdown(response.data.improvedResumeMarkdown);
        setImprovedAts(response.data.improvedAts);
        setDocxBytesBase64(response.data.docxBytesBase64);
        
        // Determine a good output filename
        const jobTitle = response.data.scrapedJobData?.["Job Title"] || 'Job';
        const company = response.data.scrapedJobData?.["Company"] || 'Company';
        setOutputFilename(`${jobTitle}_${company}_Resume.docx`.replace(/[^a-zA-Z0-9_.-]/g, '_'));

        setAppStep('results_job_data'); // Or whichever step is appropriate to show first results
      } else {
        toast.error(response.error || "Backend processing failed. Please try again.");
        setAppStep('error');
      }
    } catch (error: unknown) {
      toast.error(`An unexpected error occurred: ${error instanceof Error ? error.message : "Unknown error"}`);
      setAppStep('error');
    }
  }, [jobInputUIMode, jobUrl, jobDescription, resumeFile, knowledgeBaseFiles]);

  const handleProceedToCvPreview = useCallback(() => setAppStep('results_cv_preview'), []);

  const handleProceedToAtsOriginal = useCallback(async () => {
    setAppStep('loading'); 
    setIsLoadingMessage('Calculating Pre-Enhancement ATS Signature...');
    try {
      await new Promise(resolve => setTimeout(resolve, 1500));
      const mockOriginalAts = { 
        score: 62, 
        summary: "Strong physics background, but lacks specific Q-Sharp project examples.", 
        recommendations: ["Highlight Q-Sharp algorithm development experience.", "Add metrics for entanglement stability improvements achieved."] 
      };
      setOriginalAts(mockOriginalAts);
      setAppStep('results_ats_original');
    } catch (error: unknown) {
      toast.error((error instanceof Error ? error.message : "Unknown error") || "ATS analysis failed."); 
      setAppStep('error'); 
    }
  }, []);
  
  const handleProceedToGenerateResume = useCallback(async () => {
    setAppStep('loading'); 
    setIsLoadingMessage('Engaging AI Core for Resume Synthesis...');
    try {
      await new Promise(resolve => setTimeout(resolve, 2800));
      const mockImprovedResume = `## Dr. Aris Thorne\n### Quantum Entanglement Specialist\n\n**Contact:** a.thorne@nexus.corp | Orbital Station Prime | Clearance: Gamma-7\n\n#### Quantum Communications Expert\nAccomplished Quantum Physicist with 7 years' experience specializing in quantum communication relays and entanglement stability. Proven ability to optimize relay performance using advanced Q-Sharp programming, achieving a 25% reduction in latency for Nexus Corp. Seeking to leverage expertise in entanglement principles to enhance Nexus Corp's interstellar communication network.\n\n#### Core Strengths\n- **Quantum Entanglement:** Relay Optimization, Stability Maintenance, Decoherence Mitigation\n- **Programming:** Q-Sharp (Advanced), Python (Quantum Libraries)\n- **Project Management:** Led 'Project Chimera' entanglement stability team (5 members)\n- **Clearance:** Active Gamma-7\n\n#### Professional Experience\n**Lead Quantum Physicist** | Nexus Corp | Orbital Station Prime | 2072 - Present\n- Developed and implemented novel Q-Sharp algorithms resulting in a **25% reduction in communication latency** across the primary relay network.\n- Managed entanglement stability for **Project Chimera**, maintaining uptime above 99.98%.\n- Authored 3 internal whitepapers on advanced entanglement protocols.`;
      const mockImprovedAts = { 
        score: 95, 
        summary: "Excellent alignment. Q-Sharp experience and quantifiable achievements prominently featured.", 
        recommendations: "Consider adding a brief 'Security Clearances' section if applicable beyond contact line." 
      };
      const mockDocxBase64 = "UEsDBBQAAAAIAAgAAAAAVVVVVQAAAAAAAAAAAAAAAAwAAAAvY29udGVudHMueG1sIKpsE...";
      setImprovedResumeMarkdown(mockImprovedResume); 
      setImprovedAts(mockImprovedAts); 
      setDocxBytesBase64(mockDocxBase64);
      setAppStep('results_resume_preview');
    } catch (error: unknown) {
      toast.error((error instanceof Error ? error.message : "Unknown error") || "AI synthesis encountered an anomaly."); 
      setAppStep('error'); 
    }
  }, []);

  const handleDownloadDocx = useCallback(() => { 
    if (!docxBytesBase64) { 
      toast.error("DOCX data stream not available."); 
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
    } catch (e: unknown) {
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