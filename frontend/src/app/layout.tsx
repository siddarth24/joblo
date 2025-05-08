// app/layout.tsx (Example)
import type { Metadata } from "next";
import { Poppins } from "next/font/google"; // Import Poppins
import "./globals.css";
import { ThemeProvider } from "next-themes";

// Configure the font weights and subsets you need
const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"], // Include desired weights
  variable: '--font-poppins', // Define a CSS variable
});

export const metadata: Metadata = {
  title: "Joblo AI Resume Optimizer",
  description: "Generate tailored, ATS-friendly resumes with AI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // Apply the font variable to the html tag
    <html lang="en" className={`${poppins.variable}`} suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} forcedTheme="dark">
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}