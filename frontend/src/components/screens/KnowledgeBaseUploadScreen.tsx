import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Send, UploadCloud, XCircle, FileText } from 'lucide-react';
import { FilePlus2 } from 'lucide-react';

interface KnowledgeBaseUploadScreenProps {
  handleAttachKbClick: () => void;
  knowledgeBaseFiles: File[];
  removeKbFile: (fileName: string) => void;
  startFullProcessing: (skipKb: boolean) => void;
  isVisible: boolean;
}

const KnowledgeBaseUploadScreen: React.FC<KnowledgeBaseUploadScreenProps> = ({
  handleAttachKbClick,
  knowledgeBaseFiles,
  removeKbFile,
  startFullProcessing,
  isVisible
}) => {
  return (
    <div 
      className="fixed inset-0 z-[95] flex flex-col items-center justify-center bg-black/90 backdrop-blur-md p-4 transition-opacity duration-300 ease-in-out" 
      style={{ opacity: isVisible ? 1 : 0, visibility: isVisible ? 'visible' : 'hidden' }}
    >
      <div className="aurora-bg opacity-30">
        <div className="aurora-gradient aurora-g1"></div>
        <div className="aurora-gradient aurora-g2"></div>
      </div>
      <div className="w-full max-w-md relative z-10">
        <Card className="bg-neutral-950/80 backdrop-blur-md border-neutral-800/60 shadow-xl">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center text-xl text-white">
              <FilePlus2 className="mr-3 h-5 w-5 text-cyan-500" /> Knowledge Files
            </CardTitle>
            <CardDescription className="text-neutral-400">Enhance with additional context (optional)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button 
              variant="outline" 
              onClick={handleAttachKbClick} 
              className="w-full justify-start border-neutral-800 text-neutral-300 bg-neutral-900/60 hover:bg-neutral-800 hover:text-white transition-colors"
            >
              <UploadCloud className="mr-2 h-4 w-4"/> Select Files (PDF, DOCX, TXT)
            </Button>
            
            {knowledgeBaseFiles.length > 0 && (
              <div className="space-y-1 max-h-36 overflow-y-auto pr-2 border border-neutral-800/60 rounded-md p-2 bg-neutral-900/30">
                <p className="text-xs text-neutral-500 mb-1">Selected files:</p>
                {knowledgeBaseFiles.map(file => (
                  <div key={file.name} className="text-xs text-neutral-300 bg-neutral-900/60 px-2 py-1.5 rounded flex items-center justify-between group hover:bg-neutral-800/60 transition-colors">
                    <span className="truncate flex items-center" title={file.name}>
                      <FileText className="h-3 w-3 mr-1.5 text-neutral-500"/>
                      {file.name}
                    </span>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={() => removeKbFile(file.name)} 
                      className="h-5 w-5 opacity-60 hover:opacity-100 text-neutral-400 hover:text-red-400 hover:bg-red-950/20"
                    >
                      <XCircle className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
          <CardFooter className="flex justify-between pt-2">
            <Button 
              variant="ghost" 
              onClick={() => startFullProcessing(true)} 
              className="text-neutral-500 hover:text-neutral-300 transition-colors"
            >
              Skip
            </Button>
            <Button 
              onClick={() => startFullProcessing(false)} 
              className="bg-cyan-700 hover:bg-cyan-600 text-white transition-colors"
            >
              Continue
              <Send className="ml-2 h-4 w-4" />
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
};

export default KnowledgeBaseUploadScreen; 