import type { Metadata } from 'next';
import './globals.css';
import { Navbar } from '../components/ui/Navbar';

export const metadata: Metadata = {
  title: 'KiraNA — Cash Flow Underwriting | NBFC Intelligence Platform',
  description:
    'AI-powered kirana store cash flow analysis and loan underwriting for NBFCs',
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>₹</text></svg>",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
      </head>
      <body className="relative min-h-screen">
        <Navbar />
        <main style={{ position: 'relative', zIndex: 1 }}>{children}</main>
      </body>
    </html>
  );
}
