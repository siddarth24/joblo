import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { motion } from "framer-motion"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium ring-offset-zinc-50 dark:ring-offset-zinc-950 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 relative overflow-hidden",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground hover:bg-primary/90 shadow-md button-3d before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent before:translate-x-[-200%] hover:before:animate-shine",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-md button-3d",
        outline:
          "border border-input/80 hover:border-primary/50 bg-zinc-50/60 dark:bg-zinc-950/60 hover:bg-accent/10 backdrop-blur-sm",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/90 shadow-md button-3d before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent before:translate-x-[-200%] hover:before:animate-shine",
        ghost:
          "hover:bg-accent/20 hover:text-accent-foreground",
        glass: 
          "glass-card backdrop-blur-lg text-foreground border border-white/10 hover:border-white/20 before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/10 before:to-transparent before:translate-x-[-200%] hover:before:animate-shine",
        link: 
          "text-primary underline-offset-4 hover:underline hover:text-primary/80",
        gradient:
          "border-0 bg-gradient-to-br from-primary via-purple-500/90 to-secondary text-white shadow-lg button-3d hover:shadow-xl hover:opacity-90 before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent before:translate-x-[-200%] hover:before:animate-shine",
        grayscale:
          "border-0 bg-zinc-800 text-zinc-300 shadow-md button-3d hover:shadow-lg hover:bg-zinc-700 before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/10 before:to-transparent before:translate-x-[-200%] hover:before:animate-shine",
      },
      size: {
        default: "h-10 px-5 py-2.5",
        sm: "h-9 rounded-md px-3 text-xs",
        lg: "h-12 rounded-lg px-8 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

if (typeof document !== "undefined") {
  if (!document.querySelector("style#button-animations")) {
    const style = document.createElement("style");
    style.id = "button-animations";
    style.innerHTML = `
      @keyframes shine {
        0% { transform: translateX(-200%); }
        100% { transform: translateX(200%); }
      }
      .animate-shine {
        animation: shine 1.5s ease-in-out;
      }
    `;
    document.head.appendChild(style);
  }
}

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
    asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props}
    />
  )
}
)
Button.displayName = "Button"

const MotionButton = React.forwardRef<
  HTMLButtonElement,
  ButtonProps & { animate?: boolean }
>(({ animate = true, className, ...props }, ref) => {
  if (!animate) {
    return <Button className={className} {...props} ref={ref} />;
  }
  
  return (
    <div className={cn("inline-block", className)}>
      <motion.div
        whileHover={{ y: -2, scale: 1.02 }}
        whileTap={{ y: 2, scale: 0.98 }}
        transition={{ type: "spring", stiffness: 400, damping: 17 }}
      >
        <Button className="w-full" {...props} ref={ref} />
      </motion.div>
    </div>
  );
});
MotionButton.displayName = "MotionButton";

export { Button, MotionButton, buttonVariants }
