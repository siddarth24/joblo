// API Service for Joblo application
// This file handles all communication with the backend API

import config from '@/config';

const API_BASE_URL = config.apiUrl;

// Types for API responses
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// LinkedIn state management
export const storeLinkedInState = async (uniqueId: string, state: any): Promise<ApiResponse<any>> => {
  try {
    const response = await fetch(`${API_BASE_URL}/linkedin/state`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        unique_id: uniqueId,
        state: state,
      }),
    });
    
    return await response.json();
  } catch (error) {
    console.error('Error storing LinkedIn state:', error);
    return { success: false, error: 'Failed to store LinkedIn state' };
  }
};

export const retrieveLinkedInState = async (uniqueId: string): Promise<ApiResponse<any>> => {
  try {
    const response = await fetch(`${API_BASE_URL}/linkedin/state/${uniqueId}`, {
      method: 'GET',
    });
    
    return await response.json();
  } catch (error) {
    console.error('Error retrieving LinkedIn state:', error);
    return { success: false, error: 'Failed to retrieve LinkedIn state' };
  }
};

export const deleteLinkedInState = async (uniqueId: string): Promise<ApiResponse<any>> => {
  try {
    const response = await fetch(`${API_BASE_URL}/linkedin/state/${uniqueId}`, {
      method: 'DELETE',
    });
    
    return await response.json();
  } catch (error) {
    console.error('Error deleting LinkedIn state:', error);
    return { success: false, error: 'Failed to delete LinkedIn state' };
  }
};

// Authentication
export const authenticateLinkedIn = async (sessionPath: string, uniqueId: string): Promise<ApiResponse<any>> => {
  try {
    const response = await fetch(`${API_BASE_URL}/authenticate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        sessionPath,
        unique_id: uniqueId,
      }),
    });
    
    return await response.json();
  } catch (error) {
    console.error('Error authenticating LinkedIn:', error);
    return { success: false, error: 'Failed to authenticate LinkedIn session' };
  }
};

// Job application processing
export const processJobApplication = async (
  formData: FormData
): Promise<ApiResponse<any>> => {
  try {
    const response = await fetch(`${API_BASE_URL}/process-job-application`, {
      method: 'POST',
      body: formData,
      // Don't set Content-Type header as it will be set automatically with boundary
    });
    
    return await response.json();
  } catch (error) {
    console.error('Error processing job application:', error);
    return { success: false, error: 'Failed to process job application' };
  }
};

// Health check
export const checkApiHealth = async (): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
    });
    
    return response.status === 200;
  } catch (error) {
    console.error('API health check failed:', error);
    return false;
  }
}; 