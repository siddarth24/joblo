import { NextRequest, NextResponse } from 'next/server';
import config from '@/config';

/**
 * API endpoint to generate an improved resume based on job description and original resume
 */
export async function POST(request: NextRequest) {
  try {
    // Get the API URL from configuration
    const apiUrl = config.apiUrl;
    
    // Get the form data from the request
    const formData = await request.formData();
    
    // Forward the request to the backend API
    const backendResponse = await fetch(`${apiUrl}/generate-resume`, {
      method: 'POST',
      body: formData,
    });
    
    if (!backendResponse.ok) {
      const errorData = await backendResponse.json();
      return NextResponse.json({ 
        success: false, 
        error: errorData.error || 'Failed to generate improved resume' 
      }, { status: backendResponse.status });
    }
    
    // Return the response from the backend
    const data = await backendResponse.json();
    return NextResponse.json({ success: true, data });
  } catch (error) {
    console.error('Error generating improved resume:', error);
    return NextResponse.json({ 
      success: false, 
      error: 'Failed to generate improved resume' 
    }, { status: 500 });
  }
} 