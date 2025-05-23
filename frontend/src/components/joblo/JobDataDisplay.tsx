import React from 'react';
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { Target } from 'lucide-react';

interface JobDataDisplayProps {
  data: any;
}

const JobDataDisplay: React.FC<JobDataDisplayProps> = ({ data }) => {
  return renderJobData(data);
};

const renderJobData = (data: any, path: string = ''): React.ReactNode => {
  const isPotentiallyKeywordRich = (key: string): boolean => {
    const lowerKey = key.toLowerCase();
    return ['requirements', 'skills', 'qualifications', 'responsibilities', 'duties', 'experience'].some(k => lowerKey.includes(k));
  };

  if (typeof data !== 'object' || data === null) {
    return <span className="text-neutral-300">{String(data)}</span>;
  }

  if (Array.isArray(data)) {
    return (
      <ul className="list-disc list-inside pl-4 space-y-1.5">
        {data.map((item, index) => (
          <li key={`${path}-${index}`} className="text-sm text-neutral-400 leading-relaxed">{renderJobData(item, `${path}[${index}]`)}</li>
        ))}
      </ul>
    );
  }

  return (
    <div className="space-y-2 pl-4 border-l border-neutral-800/50 ml-2">
      {Object.entries(data).map(([key, value]) => {
        const currentPath = path ? `${path}.${key}` : key;
        const isKeywordSection = isPotentiallyKeywordRich(key);
        return (
          <div key={key}>
            <strong className="text-sm text-cyan-400 capitalize flex items-center">
              {key.replace(/_/g, ' ')}:
              {isKeywordSection && (
                <TooltipProvider delayDuration={100}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Target className="ml-2 h-3.5 w-3.5 text-amber-400/70 inline-block" />
                    </TooltipTrigger>
                    <TooltipContent className="bg-neutral-900 text-neutral-200 border-neutral-800 text-xs">
                      <p>AI identifies keywords here</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </strong>
            <div className="mt-1">{renderJobData(value, currentPath)}</div>
          </div>
        );
      })}
    </div>
  );
};

export default JobDataDisplay; 