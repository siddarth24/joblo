"use client";

import React from "react";
import { motion } from "framer-motion";

interface PageTransitionProps {
  children: React.ReactNode;
}

export function PageTransition({ children }: PageTransitionProps) {
  return (
    <div className="page-wrapper">
      <div className="opacity-0 animate-fade-in animate-slide-up">
        {children}
      </div>
    </div>
  );
}

export function MotionWrapper({ 
  children, 
  className 
}: { 
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      {children}
    </div>
  );
} 