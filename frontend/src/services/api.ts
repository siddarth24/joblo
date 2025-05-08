import { ApiResponse, LinkedInState, JobApplicationPayload, ProcessJobApplicationResponseData } from '../types/api';

/**
 * API Configuration
 */
class ApiConfig {
  private static instance: ApiConfig;
  private _baseUrl: string;
  private _defaultHeaders: Record<string, string>;
  private _timeoutMs: number;

  private constructor() {
    this._baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5500';
    this._defaultHeaders = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    this._timeoutMs = 30000; // 30 seconds
  }

  static getInstance(): ApiConfig {
    if (!ApiConfig.instance) {
      ApiConfig.instance = new ApiConfig();
    }
    return ApiConfig.instance;
  }

  get baseUrl(): string {
    return this._baseUrl;
  }

  get defaultHeaders(): Record<string, string> {
    return { ...this._defaultHeaders };
  }

  get timeoutMs(): number {
    return this._timeoutMs;
  }

  setBaseUrl(url: string): void {
    this._baseUrl = url;
  }

  setDefaultHeader(key: string, value: string): void {
    this._defaultHeaders[key] = value;
  }

  setTimeoutMs(timeoutMs: number): void {
    this._timeoutMs = timeoutMs;
  }
}

/**
 * Fetch API wrapper with timeout and error handling
 */
async function fetchWithTimeout<T>(
  url: string,
  options: RequestInit = {},
  timeoutMs: number = ApiConfig.getInstance().timeoutMs
): Promise<ApiResponse<T>> {
  const controller = new AbortController();
  const signal = controller.signal;

  const timeoutPromise = new Promise<never>((_, reject) => {
    setTimeout(() => {
      controller.abort();
      reject(new Error('Request timeout'));
    }, timeoutMs);
  });

  try {
    const fetchPromise = fetch(url, {
      ...options,
      signal,
    });

    const response = await Promise.race([fetchPromise, timeoutPromise]);
    const data = await response.json();
    
    if (!response.ok) {
      return {
        success: false,
        error: data.error || `HTTP error! status: ${response.status}`,
        statusCode: response.status,
      };
    }

    return data as ApiResponse<T>;
  } catch (error) {
    console.error('API request failed:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * API Client for Joblo application
 */
export class ApiClient {
  private static instance: ApiClient;
  private readonly config: ApiConfig;
  
  private constructor() {
    this.config = ApiConfig.getInstance();
  }

  static getInstance(): ApiClient {
    if (!ApiClient.instance) {
      ApiClient.instance = new ApiClient();
    }
    return ApiClient.instance;
  }

  /**
   * Performs a health check on the backend.
   */
  async healthCheck(): Promise<ApiResponse<{ status: string }>> {
    return fetchWithTimeout<{ status: string }>(
      `${this.config.baseUrl}/health`,
      {
        method: 'GET',
        headers: this.config.defaultHeaders,
      }
    );
  }

  /**
   * Stores LinkedIn session state on the backend.
   * @param uniqueId - A unique identifier for the session
   * @param stateData - The LinkedIn state data to store
   */
  async storeLinkedInState(uniqueId: string, stateData: LinkedInState): Promise<ApiResponse> {
    return fetchWithTimeout(
      `${this.config.baseUrl}/linkedin/state`,
      {
        method: 'POST',
        headers: this.config.defaultHeaders,
        body: JSON.stringify({ unique_id: uniqueId, state: stateData }),
      }
    );
  }

  /**
   * Retrieves stored LinkedIn session state from the backend.
   * @param uniqueId - The unique identifier for the session
   */
  async retrieveLinkedInState(uniqueId: string): Promise<ApiResponse<LinkedInState>> {
    return fetchWithTimeout<LinkedInState>(
      `${this.config.baseUrl}/linkedin/state/${uniqueId}`,
      {
        method: 'GET',
        headers: this.config.defaultHeaders,
      }
    );
  }

  /**
   * Deletes stored LinkedIn session state from the backend.
   * @param uniqueId - The unique identifier for the session
   */
  async deleteLinkedInState(uniqueId: string): Promise<ApiResponse> {
    return fetchWithTimeout(
      `${this.config.baseUrl}/linkedin/state/${uniqueId}`,
      {
        method: 'DELETE',
        headers: this.config.defaultHeaders,
      }
    );
  }

  /**
   * Authenticates a session using a stored state file path.
   * @param uniqueId - The unique identifier for the session
   * @param sessionPath - The path to the session state file
   */
  async authenticateSession(uniqueId: string, sessionPath: string): Promise<ApiResponse> {
    return fetchWithTimeout(
      `${this.config.baseUrl}/authenticate`,
      {
        method: 'POST',
        headers: this.config.defaultHeaders,
        body: JSON.stringify({ unique_id: uniqueId, sessionPath }),
      }
    );
  }

  /**
   * Sends job application data to the backend for processing.
   * @param payload - The job application data including files
   */
  async processJobApplication(
    payload: JobApplicationPayload
  ): Promise<ApiResponse<ProcessJobApplicationResponseData>> {
    const formData = new FormData();

    // Add job details
    if (payload.jobUrl) {
      formData.append('jobUrl', payload.jobUrl);
    }
    if (payload.jobDescription) {
      formData.append('jobDescription', payload.jobDescription);
    }
    
    // Add resume file
    formData.append('resumeFile', payload.resumeFile);
    
    // Add knowledge base files if available
    if (payload.kbFiles && payload.kbFiles.length > 0) {
      payload.kbFiles.forEach((file: File) => {
        formData.append('kbFiles', file);
      });
    }

    return fetchWithTimeout<ProcessJobApplicationResponseData>(
      `${this.config.baseUrl}/process-job-application`,
      {
        method: 'POST',
        body: formData,
        // Don't set Content-Type header for FormData,
        // the browser will set it with the correct boundary
        headers: {},
      }
    );
  }
}

/**
 * Generate a unique ID (useful for creating session IDs)
 */
export function generateUniqueId(): string {
  return Math.random().toString(36).substring(2, 15) + 
         Math.random().toString(36).substring(2, 15);
}

// Export a singleton instance of the API client
export const api = ApiClient.getInstance(); 