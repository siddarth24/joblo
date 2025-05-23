import type { Metadata } from "next";
import { Poppins, Inter } from "next/font/google"; 
import "./globals.css";
import { ThemeProvider } from "next-themes";
import { PageTransition } from "@/components/ui/page-transition";
import { Toaster } from "sonner";

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: '--font-poppins', 
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: "JobloAI",
  description: "Generate tailored, ATS-friendly resumes with AI.",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${poppins.variable} ${inter.variable}`} suppressHydrationWarning>
      <body className="bg-zinc-950 min-h-screen antialiased overflow-x-hidden">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} forcedTheme="dark">
          <div className="relative z-10">
            <PageTransition>
              {children}
            </PageTransition>
            <Toaster richColors position="top-right" />
          </div>
          
          <div className="fixed inset-0 -z-10 overflow-hidden">
            <div className="absolute inset-0 bg-zinc-950"></div>
            
            <div className="absolute inset-0 opacity-30 bg-gradient-to-br from-primary/30 via-transparent to-secondary/30"></div>
            
            <div className="absolute -top-[30%] -left-[10%] w-[60%] h-[60%] rounded-full bg-primary/10 blur-3xl animate-float"></div>
            <div className="absolute -bottom-[30%] -right-[10%] w-[60%] h-[60%] rounded-full bg-secondary/10 blur-3xl animate-float" style={{ animationDelay: "-2s", animationDuration: "15s" }}></div>
            <div className="absolute top-[20%] right-[10%] w-[40%] h-[40%] rounded-full bg-accent/10 blur-2xl animate-float" style={{ animationDelay: "-4s", animationDuration: "18s" }}></div>
            
            <div className="absolute top-[50%] left-[20%] w-[20%] h-[20%] morphing-bg-1 opacity-30"></div>
            <div className="absolute bottom-[40%] right-[30%] w-[15%] h-[15%] morphing-bg-2 opacity-20"></div>
            
            <div className="absolute inset-0 bg-[url('/grid.svg')] bg-center opacity-[0.03]"></div>
            
            <div className="absolute inset-0 bg-[url('/dots.svg')] bg-center opacity-[0.025]"></div>
            
            <div className="absolute inset-0 circuit-pattern opacity-10"></div>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}