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
  recommendations: string[] | string;
}

export interface JobData {
  [key: string]: any;
} 