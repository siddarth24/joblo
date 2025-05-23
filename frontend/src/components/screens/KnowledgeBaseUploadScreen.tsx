import React from 'react';
import { Button, MotionButton } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, AnimateIn } from '@/components/ui/card';
import { ChevronRight, Upload, XCircle, FileText, Database } from 'lucide-react';
import { motion } from 'framer-motion';

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
      className="fixed inset-0 z-[95] flex flex-col items-center justify-center p-6 transition-opacity duration-500 ease-in-out" 
      style={{ opacity: isVisible ? 1 : 0, visibility: isVisible ? 'visible' : 'hidden' }}
    >
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-[40%] -left-[20%] w-[80%] h-[70%] rounded-full bg-primary/5 blur-3xl"></div>
        <div className="absolute -bottom-[40%] -right-[20%] w-[80%] h-[70%] rounded-full bg-secondary/5 blur-3xl"></div>
        <div className="absolute bottom-[30%] left-[10%] w-[30%] h-[30%] rounded-full bg-accent/5 blur-2xl"></div>
      </div>
      
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-md relative z-10"
      >
        <Card variant="glass" className="backdrop-blur-xl border-white/10">
          <CardHeader className="pb-2">
            <div className="flex items-center mb-1">
              <div className="mr-3 p-2 rounded-lg bg-secondary/10 text-secondary">
                <Database className="h-5 w-5" />
              </div>
              <CardTitle>Knowledge Enhancement</CardTitle>
            </div>
            <CardDescription>
              Add additional context materials to improve the accuracy of your generated resume (optional)
            </CardDescription>
          </CardHeader>
          
          <CardContent className="space-y-4 pt-4">
            <AnimateIn delay={0.1}>
              <Button 
                variant="outline" 
                onClick={handleAttachKbClick} 
                className="w-full justify-start h-11"
              >
                <Upload className="mr-2 h-4 w-4"/> 
                Select Files (PDF, DOCX, TXT)
              </Button>
            </AnimateIn>
            
            {knowledgeBaseFiles.length > 0 && (
              <AnimateIn delay={0.2}>
                <div className="space-y-1 max-h-48 overflow-y-auto pr-2 border border-white/20 rounded-lg p-3 bg-card/30">
                  <p className="text-xs text-muted-foreground mb-2">Selected files:</p>
                  {knowledgeBaseFiles.map(file => (
                    <div 
                      key={file.name} 
                      className="text-sm bg-card/40 px-3 py-2 rounded-md flex items-center justify-between group hover:bg-card/60 transition-colors"
                    >
                      <span className="truncate flex items-center flex-1 mr-2" title={file.name}>
                        <FileText className="h-3.5 w-3.5 mr-2 text-muted-foreground"/>
                        {file.name}
                      </span>
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => removeKbFile(file.name)} 
                        className="h-6 w-6 p-0 hover:text-destructive hover:bg-destructive/10 rounded-full"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
              </AnimateIn>
            )}
          </CardContent>
          
          <CardFooter className="flex justify-between pt-4 border-t border-white/10">
            <Button 
              variant="ghost" 
              onClick={() => startFullProcessing(true)} 
              className="text-muted-foreground hover:text-foreground"
            >
              Skip for now
            </Button>
            <MotionButton 
              variant="default"
              onClick={() => startFullProcessing(false)} 
            >
              Continue
              <ChevronRight className="ml-1 h-4 w-4" />
            </MotionButton>
          </CardFooter>
        </Card>
      </motion.div>
    </div>
  );
};

export default KnowledgeBaseUploadScreen; 