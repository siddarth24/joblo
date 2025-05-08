/**
 * Generic API response type
 */
export interface ApiResponse<T = unknown> {
  success: boolean;
  message?: string;
  error?: string;
  statusCode?: number;
  data?: T;
  state?: T; // Used by retrieve_state
  stateFile?: string; // Used by store_state
  unique_id?: string; // Used by authenticate
}

/**
 * LinkedIn state structure
 */
export interface LinkedInState {
  cookies: Record<string, unknown>[];
  localStorage: Record<string, string>;
  // Add other relevant fields as needed
}

/**
 * Job application payload structure
 */
export interface JobApplicationPayload {
  jobUrl?: string;
  jobDescription?: string;
  resumeFile: File;
  kbFiles?: File[];
}

/**
 * Scraped job data structure
 */
export interface ScrapedJobData {
  "Job Title": string;
  "Company": string;
  "Location": string;
  "Description": string;
  "Requirements": string[];
  "Preferred": string[];
  "Clearance"?: string;
  "SourceURL"?: string;
}

/**
 * ATS score data structure
 */
export interface AtsScoreData {
  score: number;
  summary: string;
  recommendations: string | string[];
}

/**
 * Process job application response data structure
 */
export interface ProcessJobApplicationResponseData {
  scrapedJobData: ScrapedJobData;
  extractedCvText: string;
  originalAts: AtsScoreData;
  improvedResumeMarkdown: string;
  improvedAts: AtsScoreData;
  docxBytesBase64: string;
} 