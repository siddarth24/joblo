import { NextRequest, NextResponse } from 'next/server';
import config from '@/config';

/**
 * API endpoint to analyze a resume against a job description for ATS scoring
 */
export async function POST(request: NextRequest) {
  try {
    // Get the API URL from configuration
    const apiUrl = config.apiUrl;
    
    // Get the form data from the request
    const formData = await request.formData();
    
    // Log form data keys for debugging
    console.log('Form data keys:', Array.from(formData.keys()));
    
    // Forward the request to the backend API
    const backendResponse = await fetch(`${apiUrl}/analyze-ats`, {
      method: 'POST',
      body: formData,
    });
    
    if (!backendResponse.ok) {
      const errorData = await backendResponse.json();
      console.error('Backend error:', errorData);
      return NextResponse.json({ 
        success: false, 
        error: errorData.error || 'Failed to analyze ATS score' 
      }, { status: backendResponse.status });
    }
    
    // Return the response from the backend
    const data = await backendResponse.json();
    console.log('API response data:', JSON.stringify(data));
    return NextResponse.json({ success: true, data });
  } catch (error) {
    console.error('Error analyzing ATS score:', error);
    return NextResponse.json({ 
      success: false, 
      error: 'Failed to analyze ATS score' 
    }, { status: 500 });
  }
} 