import "./globals.css";
import type { Metadata } from "next";
import { Toaster } from "sonner";
import { ThemeProvider, ThemeToggle } from "@/components/ui/theme-provider";
import { HistoryDrawer } from "@/components/HistoryDrawer";

export const metadata: Metadata = {
  title: "CIMSummarizer — Tristone",
  description: "AI-assisted CIM → Deal Summary",
};

// No-flash: applies theme class before first paint
const noFlashScript = `
(function(){try{var t=localStorage.getItem('cim-theme');
var s=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';
var c=t||s;document.documentElement.classList.toggle('dark',c==='dark');
document.documentElement.style.colorScheme=c;}catch(e){}})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: noFlashScript }} />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ThemeProvider>
          <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur-md no-print">
            <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
              <a href="/" className="flex items-center gap-3">
                <img
                  src="/tristone-logo.png"
                  alt="Tristone"
                  className="h-6 w-auto dark:brightness-0 dark:invert"
                />
                <span className="text-muted-foreground/50 select-none hidden sm:inline">|</span>
                <span className="font-semibold tracking-tight hidden sm:inline">CIMSummarizer</span>
              </a>
              <div className="flex items-center gap-2">
                <a href="/" className="text-sm text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-md hover:bg-muted">
                  New Deal
                </a>
                <HistoryDrawer />
                <ThemeToggle />
              </div>
            </div>
          </header>
          <main className="max-w-7xl mx-auto p-6">{children}</main>
          <Toaster richColors position="top-right" theme="system" />
        </ThemeProvider>
      </body>
    </html>
  );
}
