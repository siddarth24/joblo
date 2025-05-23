import React, { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import NecktieIcon from '@/components/ui/NecktieIcon';

interface LoadingScreenProps {
  isLoading: boolean;
  loadingMessage: string;
}

const LoadingScreen: React.FC<LoadingScreenProps> = ({ isLoading, loadingMessage }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [progress, setProgress] = React.useState(10);
  const [loadingTexts, setLoadingTexts] = React.useState<string[]>([
    "Analyzing job requirements...",
    "Extracting key skills...",
    "Parsing resume content...",
    "Matching qualifications...",
    "Optimizing ATS score...",
    "Generating tailored content..."
  ]);
  const [currentTextIndex, setCurrentTextIndex] = React.useState(0);
  
  const [mousePosition, setMousePosition] = React.useState({ x: 0, y: 0 });
  
  React.useEffect(() => {
    const timer = setInterval(() => {
      setProgress((prevProgress) => {
        const increment = Math.max(1, 15 - Math.floor(prevProgress / 10));
        const nextProgress = Math.min(95, prevProgress + increment);
        return nextProgress;
      });
    }, 800);
    
    return () => clearInterval(timer);
  }, []);
  
  React.useEffect(() => {
    const textTimer = setInterval(() => {
      setCurrentTextIndex((prevIndex) => (prevIndex + 1) % loadingTexts.length);
    }, 2500);
    
    return () => clearInterval(textTimer);
  }, [loadingTexts]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      
      const rect = containerRef.current.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = ((e.clientY - rect.top) / rect.height) * 2 - 1;
      
      setMousePosition({ x, y });
    };
    
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);
  
  const particles = React.useMemo(() => {
    return Array.from({ length: 30 }).map((_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 4 + 1,
      duration: Math.random() * 20 + 10,
      delay: Math.random() * 5,
      color: i % 5 === 0 ? 'primary' : i % 3 === 0 ? 'secondary' : 'accent'
    }));
  }, []);
  
  const floatingElements = React.useMemo(() => {
    const elements = [
      { type: 'cube', size: 40, x: 15, y: 20, delay: 0, duration: 25 },
      { type: 'sphere', size: 30, x: 80, y: 65, delay: 2, duration: 20 },
      { type: 'pyramid', size: 35, x: 25, y: 75, delay: 4, duration: 22 },
      { type: 'ring', size: 45, x: 85, y: 25, delay: 1, duration: 30 },
      { type: 'document', size: 25, x: 50, y: 85, delay: 3, duration: 18 }
    ];
    
    return elements;
  }, []);

  return (
    <AnimatePresence>
      {isLoading && (
        <motion.div 
          ref={containerRef}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center p-6 perspective-container"
          style={{ perspective: '1200px' }}
        >
          <div className="absolute inset-0 overflow-hidden bg-zinc-950">
            <div 
              className="absolute inset-0 mesh-gradient opacity-70"
              style={{ 
                backgroundPosition: `${50 + mousePosition.x * 10}% ${50 + mousePosition.y * 10}%` 
              }}
            />
            
            <div className="absolute -top-[20%] -left-[20%] w-[70%] h-[70%] rounded-full bg-primary/5 blur-3xl animate-float" 
              style={{ 
                transform: `translate(${mousePosition.x * 20}px, ${mousePosition.y * 20}px)`,
                animationDuration: '25s' 
              }}
            />
            <div className="absolute -bottom-[30%] -right-[20%] w-[80%] h-[80%] rounded-full bg-secondary/5 blur-3xl animate-float" 
              style={{ 
                transform: `translate(${mousePosition.x * -15}px, ${mousePosition.y * -15}px)`,
                animationDelay: '-5s', 
                animationDuration: '30s' 
              }}
            />
            
            <div className="absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[length:20px_20px]"></div>
            
            {particles.map((particle) => (
              <motion.div
                key={particle.id}
                className={`absolute rounded-full ${
                  particle.color === 'primary' 
                    ? 'bg-primary/30' 
                    : particle.color === 'secondary' 
                    ? 'bg-secondary/30' 
                    : 'bg-accent/30'
                }`}
                style={{
                  left: `${particle.x}%`,
                  top: `${particle.y}%`,
                  width: `${particle.size}px`,
                  height: `${particle.size}px`,
                  boxShadow: `0 0 ${particle.size * 2}px ${particle.size / 2}px ${
                    particle.color === 'primary' 
                      ? 'rgba(var(--primary), 0.3)' 
                      : particle.color === 'secondary' 
                      ? 'rgba(var(--secondary), 0.3)' 
                      : 'rgba(var(--accent), 0.3)'
                  }`,
                  filter: `blur(${particle.size <= 2 ? 0 : particle.size / 4}px)`
                }}
                animate={{
                  y: [`${particle.y}%`, `${particle.y - 15 - particle.size}%`, `${particle.y}%`],
                  x: [`${particle.x}%`, `${particle.x + (Math.random() * 10 - 5)}%`, `${particle.x}%`],
                  opacity: [0.3, 0.6, 0.3],
                  scale: [1, 1.2, 1]
                }}
                transition={{
                  duration: particle.duration,
                  delay: particle.delay,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
            ))}
            
            {floatingElements.map((element, index) => (
              <motion.div
                key={`element-${index}`}
                className="absolute"
                style={{
                  left: `${element.x}%`,
                  top: `${element.y}%`,
                  zIndex: 1
                }}
                animate={{
                  y: [0, -20, 0],
                  x: [0, element.type === 'cube' ? 10 : -10, 0],
                  rotateX: [0, 360, 0],
                  rotateY: [0, 360, 0],
                  rotateZ: element.type === 'ring' ? [0, 360, 0] : [0, 0, 0]
                }}
                transition={{
                  duration: element.duration,
                  delay: element.delay,
                  repeat: Infinity,
                  ease: "linear"
                }}
              >
                {element.type === 'cube' && (
                  <div className="relative w-[40px] h-[40px] transform-style-3d">
                    {[
                      { transform: 'translateZ(20px)', bg: 'bg-primary/10' },
                      { transform: 'rotateY(180deg) translateZ(20px)', bg: 'bg-primary/10' },
                      { transform: 'rotateY(90deg) translateZ(20px)', bg: 'bg-secondary/10' },
                      { transform: 'rotateY(-90deg) translateZ(20px)', bg: 'bg-secondary/10' },
                      { transform: 'rotateX(90deg) translateZ(20px)', bg: 'bg-accent/10' },
                      { transform: 'rotateX(-90deg) translateZ(20px)', bg: 'bg-accent/10' },
                    ].map((face, i) => (
                      <div
                        key={`face-${i}`}
                        className={`absolute w-full h-full border border-white/20 ${face.bg} backdrop-blur-md`}
                        style={{ transform: face.transform }}
                      />
                    ))}
                  </div>
                )}
                
                {element.type === 'document' && (
                  <div className="relative w-[30px] h-[38px]">
                    <div className="absolute inset-0 bg-white/5 border border-white/20 rounded-sm shadow-lg backdrop-blur-sm">
                      <div className="h-2 w-[70%] mx-auto mt-2 bg-primary/30 rounded-sm"></div>
                      <div className="h-1 w-[90%] mx-auto mt-2 bg-white/20 rounded-sm"></div>
                      <div className="h-1 w-[60%] mx-auto mt-1 bg-white/20 rounded-sm"></div>
                      <div className="h-1 w-[80%] mx-auto mt-1 bg-white/20 rounded-sm"></div>
                    </div>
                    <div className="absolute top-0 right-0 border-t-[12px] border-r-[12px] border-t-white/10 border-r-transparent"></div>
                  </div>
                )}
                
                {element.type === 'sphere' && (
                  <div className="relative w-[30px] h-[30px] rounded-full bg-gradient-to-br from-secondary/20 to-primary/20 border border-white/10 shadow-lg backdrop-blur-sm">
                    <div className="absolute top-[10%] left-[10%] w-[30%] h-[30%] rounded-full bg-white/20"></div>
                  </div>
                )}
                
                {element.type === 'pyramid' && (
                  <div className="pyramid-3d">
                    <div className="pyramid-face pyramid-face-1 bg-primary/10 border border-white/20 backdrop-blur-sm"></div>
                    <div className="pyramid-face pyramid-face-2 bg-secondary/10 border border-white/20 backdrop-blur-sm"></div>
                    <div className="pyramid-face pyramid-face-3 bg-accent/10 border border-white/20 backdrop-blur-sm"></div>
                    <div className="pyramid-face pyramid-face-4 bg-primary/10 border border-white/20 backdrop-blur-sm"></div>
                  </div>
                )}
                
                {element.type === 'ring' && (
                  <div className="relative w-[40px] h-[40px]">
                    <div className="absolute inset-0 rounded-full border-[3px] border-secondary/40 backdrop-blur-sm"></div>
                    <div className="absolute inset-[7px] rounded-full border-[3px] border-primary/40 backdrop-blur-sm"></div>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
          
          <motion.div 
            initial={{ opacity: 0, scale: 0.9, rotateX: -20 }}
            animate={{ 
              opacity: 1, 
              scale: 1, 
              rotateY: mousePosition.x * 5,
              rotateX: mousePosition.y * -5
            }}
            transition={{ duration: 0.5, type: 'spring' }}
            className="glass-card-pro rounded-xl p-8 shadow-2xl backdrop-blur-lg relative z-10 w-full max-w-md text-center transform-gpu"
            style={{ 
              transformStyle: 'preserve-3d',
              boxShadow: `
                0 10px 30px -5px rgba(0, 0, 0, 0.3), 
                0 0 80px -20px rgba(var(--primary), 0.25), 
                0 0 40px -10px rgba(var(--secondary), 0.2)
              `
            }}
          >
            <motion.div 
              className="relative flex justify-center items-center mb-8"
              style={{ perspective: '1000px', transformStyle: 'preserve-3d' }}
              animate={{ rotateY: [0, 360], rotateX: [5, -5, 5] }}
              transition={{ rotateY: { duration: 20, repeat: Infinity, ease: 'linear' }, rotateX: { duration: 6, repeat: Infinity, ease: 'easeInOut' } }}
            >
              <motion.div
                className="absolute w-[120px] h-[120px] rounded-full border border-primary/30"
                animate={{ rotateZ: 360, rotateY: 45 }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                style={{ transformStyle: 'preserve-3d' }}
              />
              <motion.div
                className="absolute w-[90px] h-[90px] rounded-full border border-secondary/30"
                animate={{ rotateZ: -360, rotateX: 45 }}
                transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
                style={{ transformStyle: 'preserve-3d' }}
              />
              
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={`orbit-particle-${i}`}
                  className="absolute rounded-full"
                  style={{ 
                    width: '8px', 
                    height: '8px',
                    transformStyle: 'preserve-3d',
                    background: i === 0 
                      ? 'hsl(var(--primary))' 
                      : i === 1 
                      ? 'hsl(var(--secondary))' 
                      : 'hsl(var(--accent))',
                    boxShadow: i === 0 
                      ? '0 0 10px 2px rgba(var(--primary), 0.7)' 
                      : i === 1 
                      ? '0 0 10px 2px rgba(var(--secondary), 0.7)' 
                      : '0 0 10px 2px rgba(var(--accent), 0.7)',
                  }}
                  animate={{ 
                    z: [30, -30, 30],
                  }}
                  transition={{ 
                    z: { duration: 8, repeat: Infinity, ease: 'easeInOut', delay: i * 2.5 }
                  }}
                >
                  <motion.div
                    animate={{
                      rotate: 360,
                      translateX: 55,
                    }}
                    transition={{ duration: 8, repeat: Infinity, ease: "linear", delay: i * 2.5 }}
                  />
                </motion.div>
              ))}

              <motion.div 
                className="relative z-10"
                animate={{ 
                  scale: [1, 1.05, 1],
                  rotate: [0, 5, 0, -5, 0]
                }}
                transition={{ 
                  scale: { duration: 4, repeat: Infinity, ease: "easeInOut" },
                  rotate: { duration: 6, repeat: Infinity, ease: "easeInOut" }
                }}
              >
                <NecktieIcon 
                  width={60}
                  height={60}
                  glowEffect={true}
                  gradientColors={{
                    start: "hsl(262 83% 58%)",
                    middle: "hsl(199 89% 48%)",
                    end: "hsl(320 95% 60%)"
                  }}
                />
              </motion.div>
            </motion.div>
            
            <motion.h2 
              className="text-2xl sm:text-3xl font-bold mb-2 text-gradient bg-gradient-to-r from-primary via-secondary to-primary bg-clip-text text-transparent"
              animate={{ 
                backgroundPosition: ['0% center', '100% center', '0% center'],
                opacity: [0.9, 1, 0.9]
              }}
              transition={{ 
                backgroundPosition: { duration: 8, repeat: Infinity, ease: "easeInOut" },
                opacity: { duration: 3, repeat: Infinity, ease: "easeInOut" }
              }}
            >
              {loadingMessage}
            </motion.h2>
            
            <AnimatePresence mode="wait">
              <motion.div
                key={currentTextIndex}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.5 }}
                className="h-6 mb-8"
              >
                <p className="text-sm text-white/70">{loadingTexts[currentTextIndex]}</p>
              </motion.div>
            </AnimatePresence>
            
            <div className="space-y-6">
              <div className="relative h-3 w-full bg-black/30 rounded-full overflow-hidden border border-white/10">
                <div className="absolute inset-0 backdrop-blur-sm"></div>
                
                <motion.div
                  className="absolute top-0 left-0 h-full rounded-full"
                  style={{
                    background: `linear-gradient(90deg, 
                      hsl(var(--primary)) 0%, 
                      hsl(var(--secondary)) 50%, 
                      hsl(var(--accent)) 100%
                    )`,
                    backgroundSize: '200% 100%',
                  }}
                  animate={{ 
                    width: `${progress}%`,
                    backgroundPosition: ['0% center', '100% center']
                  }}
                  transition={{ 
                    width: { duration: 0.8, ease: "easeOut" },
                    backgroundPosition: { duration: 3, repeat: Infinity, ease: "linear" }
                  }}
                />
                
                <motion.div
                  className="absolute top-0 left-0 h-full w-full bg-white/20 rounded-full"
                  animate={{ 
                    opacity: [0, 0.5, 0],
                    scaleX: [0, 1, 0],
                    translateX: ['-100%', '100%']
                  }}
                  transition={{ 
                    duration: 2, 
                    repeat: Infinity, 
                    ease: "easeInOut" 
                  }}
                />
              </div>
              
              <div className="flex justify-center gap-3">
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="h-3 w-3 rounded-full"
                    style={{
                      background: i === 0 
                        ? 'hsl(var(--primary))' 
                        : i === 1 
                        ? 'hsl(var(--secondary))' 
                        : 'hsl(var(--accent))',
                      boxShadow: i === 0 
                        ? '0 0 10px rgba(var(--primary), 0.7)' 
                        : i === 1 
                        ? '0 0 10px rgba(var(--secondary), 0.7)' 
                        : '0 0 10px rgba(var(--accent), 0.7)',
                    }}
                    animate={{ 
                      scale: [1, 1.5, 1],
                      opacity: [0.7, 1, 0.7] 
                    }}
                    transition={{ 
                      duration: 1.4, 
                      repeat: Infinity, 
                      delay: i * 0.3,
                      ease: "easeInOut"
                    }}
                  />
                ))}
              </div>
            </div>
            
            <motion.div 
              className="mt-6 text-xs text-white/50 flex justify-between items-center"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1 }}
            >
              <span>Starting analysis</span>
              <span className="font-mono">{progress}%</span>
              <span>Finalizing</span>
            </motion.div>
          </motion.div>
          
          <motion.p 
            className="text-sm mt-8 relative z-10"
            animate={{ 
              opacity: [0.6, 0.8, 0.6],
              y: [0, -5, 0]
            }}
            transition={{ 
              duration: 4, 
              repeat: Infinity, 
              ease: "easeInOut" 
            }}
          >
            <span className="text-gradient bg-gradient-to-r from-primary via-white to-secondary bg-clip-text text-transparent">
              Optimizing your resume for maximum impact
            </span>
          </motion.p>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default LoadingScreen; 