import * as React from "react"
import { motion, HTMLMotionProps } from "framer-motion"

import { cn } from "@/lib/utils"

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "glass" | "frosted" | "gradient" | "outline" | "accent";
  animate?: boolean;
  hover?: boolean;
}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = "default", animate = true, hover = true, ...props }, ref) => {
    const baseStyles = "flex flex-col gap-4 rounded-xl p-6 text-zinc-900 dark:text-zinc-100";
    
    const variantStyles = {
      default: "bg-white dark:bg-zinc-900 border border-white/30 shadow-sm",
      glass: "glass-card bg-white/70 dark:bg-zinc-900/70 backdrop-blur-lg border border-white/10",
      frosted: "glass-card bg-white/50 dark:bg-zinc-900/50 backdrop-blur-xl border border-white/20 shadow-xl",
      gradient: "relative border-0 before:absolute before:inset-0 before:-z-10 before:rounded-xl before:bg-gradient-to-br before:from-indigo-500/20 before:via-blue-500/20 before:to-pink-500/20 before:blur-[2px] bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md",
      outline: "bg-transparent border border-indigo-500/30 shadow-sm hover:border-indigo-500/50",
      accent: "bg-pink-500/10 border border-pink-500/20 shadow-sm"
    };
    
    const hoverStyles = hover 
      ? "transition-all duration-300 hover:shadow-md hover:-translate-y-1" 
      : "";
    
    const animationStyles = animate 
      ? "opacity-0 animate-fade-in" 
      : "";
    
    const styles = cn(
      baseStyles, 
      variantStyles[variant],
      hoverStyles,
      animationStyles,
      className
    );
    
  return (
    <div
      ref={ref}
      data-slot="card"
      className={styles}
      {...props}
    />
    );
}
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<
  HTMLDivElement, 
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-slot="card-header"
      className={cn(
        "flex flex-col space-y-1.5 pb-4",
        className
      )}
      {...props}
    />
  );
});
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => {
  return (
    <h3
      ref={ref}
      data-slot="card-title"
      className={cn("text-xl font-semibold leading-none tracking-tight", className)}
      {...props}
    />
  );
});
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => {
  return (
    <p
      ref={ref}
      data-slot="card-description"
      className={cn("text-sm text-zinc-500 dark:text-zinc-400", className)}
      {...props}
    />
  );
});
CardDescription.displayName = "CardDescription";

const CardAction = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-slot="card-action"
      className={cn(
        "flex items-center justify-end",
        className
      )}
      {...props}
    />
  );
});
CardAction.displayName = "CardAction";

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-slot="card-content"
      className={cn("", className)}
      {...props}
    />
  );
});
CardContent.displayName = "CardContent";

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-slot="card-footer"
      className={cn("flex items-center justify-between pt-4", className)}
      {...props}
    />
  );
});
CardFooter.displayName = "CardFooter";

// Animation wrapper component that can be used with any of the card components
const AnimateIn = ({ 
  children, 
  className,
  delay = 0, 
  ...props 
}: { 
  children: React.ReactNode, 
  className?: string,
  delay?: number 
} & Omit<HTMLMotionProps<"div">, "children" | "className" | "initial" | "animate" | "transition">) => {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ 
        duration: 0.4, 
        delay,
        ease: [0.25, 0.1, 0.25, 1.0] 
      }}
      {...props}
    >
      {children}
    </motion.div>
  );
};

// Type for card variants
type CardVariant = CardProps["variant"];

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
  AnimateIn,
  type CardVariant
}
