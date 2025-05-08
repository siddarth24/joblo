const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5500';

export interface LinkedInState {
  // Define the structure of LinkedIn state data based on what's stored/retrieved
  cookies: Record<string, unknown>[]; // Changed from any[] to Record<string, unknown>[]
  localStorage: Record<string, string>; // Example
  // Add other relevant fields
}

export interface ApiResponse<T = unknown> {
  success: boolean;
  message?: string;
  error?: string;
  data?: T;
  state?: T; // Used by retrieve_state
  stateFile?: string; // Used by store_state
  unique_id?: string; // Used by authenticate
}

/**
 * Performs a health check on the backend.
 */
export const healthCheck = async (): Promise<ApiResponse<{ status: string }>> => {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Health check failed:", error);
    return { success: false, error: error instanceof Error ? error.message : "Unknown error" };
  }
};

/**
 * Stores LinkedIn session state on the backend.
 * @param uniqueId A unique identifier for the session.
 * @param stateData The LinkedIn state data to store.
 */
export const storeLinkedInState = async (uniqueId: string, stateData: LinkedInState): Promise<ApiResponse> => {
  try {
    const response = await fetch(`${API_BASE_URL}/linkedin/state`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ unique_id: uniqueId, state: stateData }),
    });
    return await response.json();
  } catch (error) {
    console.error("Failed to store LinkedIn state:", error);
    return { success: false, error: error instanceof Error ? error.message : "Unknown error" };
  }
};

/**
 * Retrieves stored LinkedIn session state from the backend.
 * @param uniqueId The unique identifier for the session.
 */
export const retrieveLinkedInState = async (uniqueId: string): Promise<ApiResponse<LinkedInState>> => {
  try {
    const response = await fetch(`${API_BASE_URL}/linkedin/state/${uniqueId}`);
    // The backend returns 404 for not found, which is a valid scenario.
    // The actual success/error is in the JSON body.
    return await response.json();
  } catch (error) {
    console.error("Failed to retrieve LinkedIn state:", error);
    return { success: false, error: error instanceof Error ? error.message : "Unknown error" };
  }
};

/**
 * Deletes stored LinkedIn session state from the backend.
 * @param uniqueId The unique identifier for the session.
 */
export const deleteLinkedInState = async (uniqueId: string): Promise<ApiResponse> => {
  try {
    const response = await fetch(`${API_BASE_URL}/linkedin/state/${uniqueId}`, {
      method: 'DELETE',
    });
    return await response.json();
  } catch (error) {
    console.error("Failed to delete LinkedIn state:", error);
    return { success: false, error: error instanceof Error ? error.message : "Unknown error" };
  }
};

/**
 * Authenticates a session using a stored state file path.
 * @param uniqueId The unique identifier for the session.
 * @param sessionPath The path to the session state file (as returned by storeLinkedInState).
 */
export const authenticateSession = async (uniqueId: string, sessionPath: string): Promise<ApiResponse> => {
  try {
    const response = await fetch(`${API_BASE_URL}/authenticate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ unique_id: uniqueId, sessionPath: sessionPath }),
    });
    return await response.json();
  } catch (error) {
    console.error("Authentication failed:", error);
    return { success: false, error: error instanceof Error ? error.message : "Unknown error" };
  }
};

// Example of how you might generate a unique ID on the client-side if needed
export const generateUniqueId = (): string => {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
};

// --- Interfaces for Job Application Processing ---
export interface JobApplicationPayload {
  jobUrl?: string;
  jobDescription?: string;
  resumeFile: File;
  kbFiles?: File[];
}

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

export interface AtsScoreData {
  score: number;
  summary: string;
  recommendations: string[];
}

export interface ProcessJobApplicationResponseData {
  scrapedJobData: ScrapedJobData;
  extractedCvText: string;
  originalAts: AtsScoreData;
  improvedResumeMarkdown: string;
  improvedAts: AtsScoreData;
  docxBytesBase64: string;
}

/**
 * Sends job application data to the backend for processing.
 * @param payload The job application data including files.
 */
export const processJobApplication = async (
  payload: JobApplicationPayload
): Promise<ApiResponse<ProcessJobApplicationResponseData>> => {
  const formData = new FormData();

  if (payload.jobUrl) {
    formData.append('jobUrl', payload.jobUrl);
  }
  if (payload.jobDescription) {
    formData.append('jobDescription', payload.jobDescription);
  }
  formData.append('resumeFile', payload.resumeFile);
  if (payload.kbFiles && payload.kbFiles.length > 0) {
    payload.kbFiles.forEach(file => {
      formData.append('kbFiles', file);
    });
  }

  try {
    const response = await fetch(`${API_BASE_URL}/process-job-application`, {
      method: 'POST',
      body: formData, // FormData sets Content-Type to multipart/form-data automatically
    });
    return await response.json();
  } catch (error) {
    console.error("Process job application failed:", error);
    return { 
      success: false, 
      error: error instanceof Error ? error.message : "An unknown error occurred during processing"
    };
  }
}; 