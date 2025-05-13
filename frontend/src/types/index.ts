// Common types shared across the application

export type JobInputUIMode = 'link' | 'text';

export type AppStep = 
  | 'initial_input' 
  | 'optional_kb_upload' 
  | 'loading' 
  | 'results_job_data' 
  | 'results_cv_preview' 
  | 'results_ats_original' 
  | 'results_resume_preview' 
  | 'error';

export interface AtsScore {
  score: number;
  summary: string;
  recommendations: string | string[];
}

export interface JobData {
  [key: string]: any;
  "Job Title"?: string;
  "Company"?: string;
  "Location"?: string;
  "Description"?: string;
  "Requirements"?: string[];
  "Preferred"?: string[];
  "Clearance"?: string;
}

// API Response Types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// LinkedIn State Types
export interface LinkedInState {
  cookies: any[];
  localStorage: Record<string, any>;
  sessionStorage: Record<string, any>;
}

// User Profile Types
export interface UserProfile {
  name: string;
  email?: string;
}

// Processing Result Types
export interface ProcessingResult {
  jobData: JobData;
  extractedCvText: string;
  originalAts: AtsScore;
  improvedResumeMarkdown: string;
  improvedAts: AtsScore;
  docxBytesBase64?: string;
  outputFilename?: string;
} 